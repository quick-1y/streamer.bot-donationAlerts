///----------------------------------------------------------------------------
///   DonationAlerts live spike A. Throwaway Phase 1 probe, not product code.
///   Behavior is NOT verified live until docs/live-spikes/FINDINGS.md says so.
///   Cancel-on-Dispose host: tasks are Task.Run, waits take the token, Dispose
///   cancels, aborts owned I/O, joins with a bounded wait and never throws.
///   Every log line: SPIKE <A|B> <8-hex instance id> <MARKER> <details>.
///   Written to CPH.LogInfo and to %TEMP%/da-spike-trace.log.
///----------------------------------------------------------------------------
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;

#if EXTERNAL_EDITOR
public class CPHInline : CPHInlineBase
#else
public class CPHInline
#endif
{
    private const string Code = "A";
    private const string TraceFileName = "da-spike-trace.log";
    private const string OwnerSemaphoreName = @"Local\StreamerBot.DaSpike.Owner";
    private const string OwnerGlobalName = "daSpikeOwnerGen";
    private const string DomainDataKey = "daSpikeProbe";
    private const string HttpPortGlobalName = "daSpikeHttpPort";
    private const int DefaultHttpPort = 18554;
    private const string DictEventName = "daSpikeDict";
    private const string JsonEventName = "daSpikeJson";
    private const string NoRegEventName = "daSpikeNoReg";
    private const string TriggerCategory = "DA Spike";

    private readonly object gate = new object();
    private readonly object traceLock = new object();
    private readonly CancellationTokenSource cts = new CancellationTokenSource();
    private readonly List<Task> tasks = new List<Task>();

    private string InstanceId { get; set; } = Guid.NewGuid().ToString("N").Substring(0, 8);
    private bool NoopDispose { get; set; }
    private bool InitDone { get; set; }
    private CancellationTokenSource HeartbeatCts { get; set; }
    private Semaphore OwnerSemaphore { get; set; }
    private bool OwnerHeld { get; set; }
    private HttpListener MainHttpListener { get; set; }
    private Task HttpAcceptTask { get; set; }
    private TcpListener TcpProbeListener { get; set; }
    private Task TcpAcceptTask { get; set; }
    private TcpListener RecvListener { get; set; }
    private TcpClient RecvClient { get; set; }
    private TcpClient RecvServer { get; set; }
    private Task RecvTask { get; set; }
    private HttpListener ReproListener { get; set; }

    private static string StaticProbe;

    private void Trace(string line)
    {
        try
        {
            lock (traceLock)
            {
                string stamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture);
                File.AppendAllText(
                    Path.Combine(Path.GetTempPath(), TraceFileName),
                    stamp + " " + line + Environment.NewLine,
                    new UTF8Encoding(false));
            }
        }
        catch (Exception)
        {
            // diagnostics must never throw
        }
    }

    private string Format(string marker, string details)
    {
        string line = "SPIKE " + Code + " " + InstanceId + " " + marker;
        if (!string.IsNullOrEmpty(details))
            line += " " + details;
        return line;
    }

    private void Log(string marker, string details)
    {
        string line = Format(marker, details);
        try
        {
            CPH.LogInfo(line);
        }
        catch (Exception)
        {
            // the CPH proxy may already be gone during shutdown; the trace file still gets the line
        }
        Trace(line);
    }

    private void LogFailure(string method, Exception ex)
    {
        string typeName = ex == null ? "unknown" : ex.GetType().Name;
        Log("ERROR", "method=" + method + " type=" + typeName);
    }

    private static string Flag(bool value)
    {
        return value ? "true" : "false";
    }

    private static void Quiet(Action action)
    {
        try
        {
            action();
        }
        catch (Exception)
        {
            // best-effort cleanup inside Dispose paths
        }
    }

    private static string RandomHex()
    {
        return Guid.NewGuid().ToString("N").Substring(0, 8);
    }

    private int ResolveHttpPort()
    {
        try
        {
            int port = CPH.GetGlobalVar<int>(HttpPortGlobalName, false);
            if (port > 0 && port <= 65533)
                return port;
        }
        catch (Exception)
        {
            // fall back to the default port
        }
        return DefaultHttpPort;
    }

    private string Elevated()
    {
        try
        {
            using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
            {
                bool admin = new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
                return admin ? "true" : "false";
            }
        }
        catch (Exception)
        {
            return "unknown";
        }
    }

    private int TaskCount()
    {
        lock (gate)
            return tasks.Count;
    }

    private void TrackTask(Task task)
    {
        lock (gate)
            tasks.Add(task);
    }

    public void Init()
    {
        InitDone = true;
        bool regDict = false;
        bool regJson = false;
        try
        {
            regDict = CPH.RegisterCustomTrigger("DA Spike: Dict", DictEventName, new[] { TriggerCategory });
        }
        catch (Exception ex)
        {
            LogFailure("Init.RegisterDict", ex);
        }
        try
        {
            regJson = CPH.RegisterCustomTrigger("DA Spike: Json", JsonEventName, new[] { TriggerCategory });
        }
        catch (Exception ex)
        {
            LogFailure("Init.RegisterJson", ex);
        }

        string domainName = "unknown";
        int pid = -1;
        try
        {
            domainName = AppDomain.CurrentDomain.FriendlyName;
            pid = Process.GetCurrentProcess().Id;
        }
        catch (Exception ex)
        {
            LogFailure("Init.Domain", ex);
        }
        Log(
            "INIT",
            "domain=" + AppDomain.CurrentDomain.Id
            + " domainName=" + domainName
            + " pid=" + pid
            + " regDict=" + Flag(regDict)
            + " regJson=" + Flag(regJson));
    }

    public void Dispose()
    {
        try
        {
            Stopwatch watch = Stopwatch.StartNew();
            string mode = NoopDispose ? "noop" : "cancel";
            Log("DISPOSE-BEGIN", "mode=" + mode + " tasks=" + TaskCount());
            if (NoopDispose)
            {
                Log("DISPOSE-END", "mode=noop");
                return;
            }

            try
            {
                cts.Cancel();
            }
            catch (Exception ex)
            {
                LogFailure("Dispose.Cancel", ex);
            }

            CloseOwnedIo();

            Task[] snapshot;
            lock (gate)
                snapshot = tasks.ToArray();

            bool allDone = false;
            try
            {
                allDone = Task.WaitAll(snapshot, 2000);
            }
            catch (Exception)
            {
                allDone = false;
            }

            Log("DISPOSE-END", "mode=cancel ms=" + watch.ElapsedMilliseconds + " allDone=" + Flag(allDone));
        }
        catch (Exception)
        {
            // Dispose must never throw
        }
    }

    private void CloseOwnedIo()
    {
        // The hang-repro listener is deliberately NOT touched here: the repro must be able to
        // reproduce the old fork's hang that survives Dispose.
        try
        {
            if (HeartbeatCts != null)
                HeartbeatCts.Cancel();
        }
        catch (Exception)
        {
        }

        Quiet(() =>
        {
            if (MainHttpListener != null)
                MainHttpListener.Abort();
        });
        Quiet(() =>
        {
            if (TcpProbeListener != null)
                TcpProbeListener.Stop();
        });
        Quiet(() =>
        {
            if (RecvClient != null)
                RecvClient.Close();
        });
        Quiet(() =>
        {
            if (RecvServer != null)
                RecvServer.Close();
        });
        Quiet(() =>
        {
            if (RecvListener != null)
                RecvListener.Stop();
        });

        try
        {
            if (OwnerSemaphore != null)
            {
                if (OwnerHeld)
                {
                    OwnerSemaphore.Release();
                    OwnerHeld = false;
                }
                OwnerSemaphore.Dispose();
                OwnerSemaphore = null;
            }
        }
        catch (Exception)
        {
        }
    }

    public bool SpikeInfo()
    {
        try
        {
            string fw = "unknown";
            string sb = "unknown";
            try
            {
                fw = RuntimeInformation.FrameworkDescription;
            }
            catch (Exception ex)
            {
                LogFailure("SpikeInfo.Framework", ex);
            }
            try
            {
                sb = CPH.GetVersion();
            }
            catch (Exception ex)
            {
                LogFailure("SpikeInfo.Version", ex);
            }

            Log(
                "INFO",
                "domain=" + AppDomain.CurrentDomain.Id
                + " clr=" + Environment.Version
                + " fw=" + fw
                + " sb=" + sb
                + " culture=" + CultureInfo.CurrentCulture.Name
                + " elevated=" + Elevated()
                + " pid=" + Process.GetCurrentProcess().Id
                + " mode=" + (NoopDispose ? "noop" : "cancel")
                + " tasks=" + TaskCount()
                + " init=" + Flag(InitDone));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeInfo", ex);
            return false;
        }
    }

    public bool SpikeBgStart()
    {
        try
        {
            if (HeartbeatCts != null && !HeartbeatCts.IsCancellationRequested)
            {
                Log("BG-START", "already=true");
                return true;
            }

            HeartbeatCts = CancellationTokenSource.CreateLinkedTokenSource(cts.Token);
            CancellationToken token = HeartbeatCts.Token;
            TrackTask(Task.Run(() => HeartbeatAsync(token)));
            Log("BG-START", "already=false");
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBgStart", ex);
            return false;
        }
    }

    private async Task HeartbeatAsync(CancellationToken token)
    {
        try
        {
            int n = 0;
            while (true)
            {
                await Task.Delay(2000, token).ConfigureAwait(false);
                n++;
                Trace(Format("BG-TICK", "n=" + n));
                if (n % 5 == 0)
                    Log("BG-TICK", "n=" + n);
            }
        }
        catch (OperationCanceledException)
        {
            Trace(Format("BG-CANCELLED", string.Empty));
        }
        catch (Exception ex)
        {
            Trace(Format("BG-ERROR", "type=" + ex.GetType().Name));
        }
    }

    public bool SpikeBgStop()
    {
        try
        {
            if (HeartbeatCts != null)
                HeartbeatCts.Cancel();
            Log("BG-STOP", string.Empty);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBgStop", ex);
            return false;
        }
    }

    public bool SpikeModeCancel()
    {
        try
        {
            NoopDispose = false;
            Log("MODE", "dispose=cancel");
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeModeCancel", ex);
            return false;
        }
    }

    public bool SpikeModeNoop()
    {
        try
        {
            NoopDispose = true;
            Log("MODE", "dispose=noop");
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeModeNoop", ex);
            return false;
        }
    }

    public bool SpikeOnStarted()
    {
        try
        {
            Log("STARTED", "init=" + Flag(InitDone));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOnStarted", ex);
            return false;
        }
    }

    public bool SpikeOnExiting()
    {
        try
        {
            Log("EXITING", "init=" + Flag(InitDone));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOnExiting", ex);
            return false;
        }
    }

    public bool Execute()
    {
        try
        {
            Log("EXECUTE", string.Empty);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("Execute", ex);
            return false;
        }
    }

    public bool SpikeListenHttp()
    {
        try
        {
            if (MainHttpListener != null)
            {
                Log("HTTP-BIND", "already=true");
                return true;
            }

            int port = ResolveHttpPort();
            string hex = RandomHex();
            string prefix = "http://127.0.0.1:" + port + "/da-spike-" + hex + "/";
            HttpListener listener = new HttpListener();
            listener.Prefixes.Add(prefix);
            try
            {
                listener.Start();
            }
            catch (HttpListenerException ex)
            {
                Log("HTTP-BIND-FAIL", "code=" + ex.ErrorCode + " elevated=" + Elevated());
                Quiet(() => listener.Close());
                return false;
            }

            MainHttpListener = listener;
            Log("HTTP-BIND", "port=" + port + " elevated=" + Elevated());

            CancellationToken token = cts.Token;
            HttpAcceptTask = Task.Run(() => AcceptHttpAsync(listener, token));
            TrackTask(HttpAcceptTask);
            TrackTask(Task.Run(() => HttpRoundTrip(prefix)));

            ProbeLocalhostBind(port + 1, hex);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeListenHttp", ex);
            return false;
        }
    }

    private async Task AcceptHttpAsync(HttpListener listener, CancellationToken token)
    {
        try
        {
            while (!token.IsCancellationRequested)
            {
                HttpListenerContext context = await listener.GetContextAsync().ConfigureAwait(false);
                try
                {
                    byte[] body = Encoding.UTF8.GetBytes("ok");
                    context.Response.StatusCode = 200;
                    context.Response.ContentLength64 = body.Length;
                    context.Response.OutputStream.Write(body, 0, body.Length);
                    context.Response.Close();
                }
                catch (Exception)
                {
                    // one bad request must not end the accept loop
                }
            }
            Trace(Format("HTTP-ACCEPT-END", "kind=http reason=token"));
        }
        catch (Exception ex)
        {
            Trace(Format("HTTP-ACCEPT-END", "kind=http type=" + ex.GetType().Name));
        }
    }

    private void HttpRoundTrip(string prefix)
    {
        Stopwatch watch = Stopwatch.StartNew();
        bool ok = false;
        string failure = string.Empty;
        try
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(prefix);
            request.Timeout = 3000;
            request.Proxy = null;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                ok = response.StatusCode == HttpStatusCode.OK;
        }
        catch (Exception ex)
        {
            failure = " type=" + ex.GetType().Name;
        }
        Log("HTTP-ROUNDTRIP", "ok=" + Flag(ok) + " ms=" + watch.ElapsedMilliseconds + failure);
    }

    private void ProbeLocalhostBind(int port, string hex)
    {
        string prefix = "http://localhost:" + port + "/da-spike-probe-" + hex + "/";
        HttpListener probe = new HttpListener();
        try
        {
            probe.Prefixes.Add(prefix);
            probe.Start();
            probe.Stop();
            Log("HTTP-LOCALHOST-BIND", "ok=true");
        }
        catch (HttpListenerException ex)
        {
            Log("HTTP-LOCALHOST-BIND", "ok=false code=" + ex.ErrorCode);
        }
        catch (Exception ex)
        {
            Log("HTTP-LOCALHOST-BIND", "ok=false type=" + ex.GetType().Name);
        }
        finally
        {
            Quiet(() => probe.Close());
        }
    }

    public bool SpikeListenTcp()
    {
        try
        {
            if (TcpProbeListener != null)
            {
                Log("TCP-BIND", "already=true");
                return true;
            }

            TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
            try
            {
                listener.Start();
            }
            catch (SocketException ex)
            {
                Log("TCP-BIND-FAIL", "code=" + ex.SocketErrorCode);
                return false;
            }

            TcpProbeListener = listener;
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            Log("TCP-BIND", "port=" + port);

            CancellationToken token = cts.Token;
            TcpAcceptTask = Task.Run(() => AcceptTcpAsync(listener, token));
            TrackTask(TcpAcceptTask);
            TrackTask(Task.Run(() => TcpRoundTrip(port)));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeListenTcp", ex);
            return false;
        }
    }

    private async Task AcceptTcpAsync(TcpListener listener, CancellationToken token)
    {
        try
        {
            while (!token.IsCancellationRequested)
            {
                TcpClient client = await listener.AcceptTcpClientAsync().ConfigureAwait(false);
                Quiet(() => client.Close());
            }
            Trace(Format("HTTP-ACCEPT-END", "kind=tcp reason=token"));
        }
        catch (Exception ex)
        {
            Trace(Format("HTTP-ACCEPT-END", "kind=tcp type=" + ex.GetType().Name));
        }
    }

    private void TcpRoundTrip(int port)
    {
        Stopwatch watch = Stopwatch.StartNew();
        bool ok = false;
        string failure = string.Empty;
        try
        {
            using (TcpClient client = new TcpClient())
            {
                Task connect = client.ConnectAsync(IPAddress.Loopback, port);
                ok = connect.Wait(2000) && client.Connected;
            }
        }
        catch (Exception ex)
        {
            failure = " type=" + ex.GetType().Name;
        }
        Log("TCP-ROUNDTRIP", "ok=" + Flag(ok) + " ms=" + watch.ElapsedMilliseconds + failure);
    }

    public bool SpikePendingReceive()
    {
        try
        {
            if (RecvTask != null)
            {
                Log("RECV-PENDING", "already=true");
                return true;
            }

            TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start();
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            TcpClient client = new TcpClient();
            Task connect = client.ConnectAsync(IPAddress.Loopback, port);
            Task<TcpClient> accept = listener.AcceptTcpClientAsync();
            bool paired = connect.Wait(2000) && accept.Wait(2000);
            if (!paired)
            {
                Quiet(() => client.Close());
                Quiet(() => listener.Stop());
                Log("RECV-PENDING", "port=" + port + " paired=false");
                return false;
            }

            RecvListener = listener;
            RecvClient = client;
            RecvServer = accept.Result;
            TcpClient server = RecvServer;
            CancellationToken token = cts.Token;
            RecvTask = Task.Run(() => ReceiveAsync(server, token));
            TrackTask(RecvTask);
            Log("RECV-PENDING", "port=" + port);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikePendingReceive", ex);
            return false;
        }
    }

    private async Task ReceiveAsync(TcpClient server, CancellationToken token)
    {
        try
        {
            // The peer never sends: this read stays pending until the socket is closed.
            byte[] buffer = new byte[1];
            int read = await server.GetStream().ReadAsync(buffer, 0, 1, token).ConfigureAwait(false);
            Trace(Format("RECV-END", "read=" + read));
        }
        catch (Exception ex)
        {
            Trace(Format("RECV-END", "type=" + ex.GetType().Name));
        }
    }

    public bool SpikeAbortTiming()
    {
        try
        {
            TimeAbort("http", MainHttpListener != null, () => MainHttpListener.Abort(), HttpAcceptTask);
            MainHttpListener = null;
            HttpAcceptTask = null;

            TimeAbort("tcp", TcpProbeListener != null, () => TcpProbeListener.Stop(), TcpAcceptTask);
            TcpProbeListener = null;
            TcpAcceptTask = null;

            TimeAbort(
                "recv",
                RecvClient != null || RecvServer != null,
                () =>
                {
                    if (RecvClient != null)
                        RecvClient.Close();
                    if (RecvServer != null)
                        RecvServer.Close();
                },
                RecvTask);
            Quiet(() =>
            {
                if (RecvListener != null)
                    RecvListener.Stop();
            });
            RecvClient = null;
            RecvServer = null;
            RecvListener = null;
            RecvTask = null;
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeAbortTiming", ex);
            return false;
        }
    }

    private void TimeAbort(string kind, bool present, Action abort, Task task)
    {
        if (!present)
        {
            Log("ABORT-MS", "kind=" + kind + " skipped=true");
            return;
        }

        Stopwatch watch = Stopwatch.StartNew();
        Quiet(abort);
        bool completed = false;
        try
        {
            completed = task == null || task.Wait(3000);
        }
        catch (Exception)
        {
            completed = task != null && task.IsCompleted;
        }
        Log("ABORT-MS", "kind=" + kind + " ms=" + watch.ElapsedMilliseconds + " completed=" + Flag(completed));
    }

    public bool SpikeBlockRepro()
    {
        try
        {
            // Deliberately mirrors integration.cs ServeAndListenAuth (blocking wait on the action
            // thread) and ConnectLoop (Thread.Sleep that nothing can cancel). Phase 1 uses it once
            // (RUNSHEET S6) to reproduce the old shutdown hang. No token, not tracked, never closed.
            int port = ResolveHttpPort() + 2;
            Log("BLOCK-ENTER", "port=" + port);
            string prefix = "http://127.0.0.1:" + port + "/da-spike-block-" + RandomHex() + "/";
            HttpListener repro = new HttpListener();
            repro.Prefixes.Add(prefix);
            ReproListener = repro;
            repro.Start();
            repro.GetContext();
            Thread.Sleep(600000);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBlockRepro", ex);
            return false;
        }
    }

    private Dictionary<string, object> BuildSpikeArgs(string source)
    {
        Dictionary<string, object> values = new Dictionary<string, object>();
        values["spikeAmount"] = 22.5m;
        values["spikeCount"] = 7;
        values["spikeLong"] = 9000000000L;
        values["spikeDouble"] = 22.5d;
        values["spikeFlag"] = true;
        values["spikeText"] = "x";
        values["spikeDate"] = new DateTime(2026, 1, 2, 3, 4, 5, DateTimeKind.Utc);
        values["spike.dotted"] = "d";
        values["SpikeMixedCase"] = "m";
        values["spikeSource"] = source;
        return values;
    }

    public bool SpikeFireDict()
    {
        try
        {
            bool ok = false;
            try
            {
                CPH.TriggerCodeEvent(DictEventName, BuildSpikeArgs("dict"));
                ok = true;
            }
            catch (Exception ex)
            {
                LogFailure("SpikeFireDict.Trigger", ex);
            }
            Log("FIRE", "kind=dict ok=" + Flag(ok));
            return ok;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeFireDict", ex);
            return false;
        }
    }

    public bool SpikeFireJson()
    {
        try
        {
            bool ok = false;
            try
            {
                CPH.TriggerCodeEvent(JsonEventName, JsonConvert.SerializeObject(BuildSpikeArgs("json")));
                ok = true;
            }
            catch (Exception ex)
            {
                LogFailure("SpikeFireJson.Trigger", ex);
            }
            Log("FIRE", "kind=json ok=" + Flag(ok));
            return ok;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeFireJson", ex);
            return false;
        }
    }

    public bool SpikeFireBackground()
    {
        try
        {
            TrackTask(Task.Run(() =>
            {
                bool ok = false;
                try
                {
                    CPH.TriggerCodeEvent(DictEventName, BuildSpikeArgs("background"));
                    ok = true;
                }
                catch (Exception ex)
                {
                    LogFailure("SpikeFireBackground.Trigger", ex);
                }
                Log(
                    "FIRE",
                    "kind=background thread=" + Thread.CurrentThread.ManagedThreadId
                    + " pool=" + Flag(Thread.CurrentThread.IsThreadPoolThread)
                    + " ok=" + Flag(ok));
            }));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeFireBackground", ex);
            return false;
        }
    }

    public bool SpikeFireUnregistered()
    {
        try
        {
            bool ok = false;
            try
            {
                CPH.TriggerCodeEvent(NoRegEventName, BuildSpikeArgs("noreg"));
                ok = true;
            }
            catch (Exception ex)
            {
                LogFailure("SpikeFireUnregistered.Trigger", ex);
            }
            Log("FIRE", "kind=noreg ok=" + Flag(ok));
            return ok;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeFireUnregistered", ex);
            return false;
        }
    }

    public bool SpikeDumpArgs()
    {
        try
        {
            if (args == null)
            {
                Log("DUMP", "args=null");
                return true;
            }

            List<string> spikeKeys = new List<string>();
            int other = 0;
            foreach (string key in args.Keys)
            {
                if (key != null && key.IndexOf("spike", StringComparison.OrdinalIgnoreCase) >= 0)
                    spikeKeys.Add(key);
                else
                    other++;
            }
            spikeKeys.Sort(StringComparer.Ordinal);

            // Only the type of spike* values is logged. Names and values of every other key stay
            // out of the log because Streamer.bot adds broadcaster/account data to action args.
            foreach (string key in spikeKeys)
            {
                object value = args[key];
                Log("DUMP", "key=" + key + " type=" + (value == null ? "null" : value.GetType().FullName));
            }
            Log("DUMP-OTHER", "count=" + other);

            bool gotDecimal = false;
            bool gotInt = false;
            try
            {
                decimal amount;
                gotDecimal = CPH.TryGetArg<decimal>("spikeAmount", out amount);
            }
            catch (Exception)
            {
                gotDecimal = false;
            }
            try
            {
                int count;
                gotInt = CPH.TryGetArg<int>("spikeCount", out count);
            }
            catch (Exception)
            {
                gotInt = false;
            }
            Log("DUMP-TRYGET", "decimal=" + Flag(gotDecimal) + " int=" + Flag(gotInt));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeDumpArgs", ex);
            return false;
        }
    }

    public bool SpikeOwnSemTry()
    {
        try
        {
            if (OwnerSemaphore != null)
            {
                Log("OWN-SEM", "acquired=" + Flag(OwnerHeld) + " already=true");
                return true;
            }

            bool createdNew;
            OwnerSemaphore = new Semaphore(1, 1, OwnerSemaphoreName, out createdNew);
            OwnerHeld = OwnerSemaphore.WaitOne(0);
            Log("OWN-SEM", "acquired=" + Flag(OwnerHeld) + " createdNew=" + Flag(createdNew));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOwnSemTry", ex);
            return false;
        }
    }

    public bool SpikeOwnSemRelease()
    {
        try
        {
            bool released = false;
            if (OwnerSemaphore != null && OwnerHeld)
            {
                OwnerSemaphore.Release();
                OwnerHeld = false;
                released = true;
            }
            Log("OWN-SEM", "released=" + Flag(released));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOwnSemRelease", ex);
            return false;
        }
    }

    public bool SpikeOwnGenClaim()
    {
        try
        {
            CPH.SetGlobalVar(OwnerGlobalName, InstanceId, false);
            Log("OWN-GEN", "claimed=" + InstanceId);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOwnGenClaim", ex);
            return false;
        }
    }

    public bool SpikeOwnGenCheck()
    {
        try
        {
            string seen = CPH.GetGlobalVar<string>(OwnerGlobalName, false);
            Log("OWN-GEN", "seen=" + (seen ?? string.Empty) + " mine=" + Flag(seen == InstanceId));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOwnGenCheck", ex);
            return false;
        }
    }

    public bool SpikeOwnStatic()
    {
        try
        {
            string before = StaticProbe;
            if (StaticProbe == null)
                StaticProbe = InstanceId;
            AppDomain.CurrentDomain.SetData(DomainDataKey, InstanceId);
            Log(
                "OWN-STATIC",
                "set=" + InstanceId
                + " staticBefore=" + (before ?? "null")
                + " domain=" + AppDomain.CurrentDomain.Id);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeOwnStatic", ex);
            return false;
        }
    }

    public bool SpikeExecByName()
    {
        try
        {
            ExecProbe("action-name", "SPIKE | Runtime A");
            ExecProbe("code-name", "DaSpikeA");
            ExecProbe("wrong-name", "SPIKE | No Such Action");
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeExecByName", ex);
            return false;
        }
    }

    private void ExecProbe(string label, string target)
    {
        string result;
        try
        {
            result = Flag(CPH.ExecuteMethod(target, "SpikeInfo"));
        }
        catch (Exception ex)
        {
            result = ex.GetType().Name;
        }
        Log("EXEC", "target=" + label + " result=" + result);
    }
}
