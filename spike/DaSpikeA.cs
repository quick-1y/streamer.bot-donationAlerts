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
            + " regDict=" + regDict
            + " regJson=" + regJson);
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

            Log("DISPOSE-END", "mode=cancel ms=" + watch.ElapsedMilliseconds + " allDone=" + allDone);
        }
        catch (Exception)
        {
            // Dispose must never throw
        }
    }

    private void CloseOwnedIo()
    {
        try
        {
            if (HeartbeatCts != null)
                HeartbeatCts.Cancel();
        }
        catch (Exception)
        {
        }

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
                + " init=" + InitDone);
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
            Log("STARTED", "init=" + InitDone);
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
            Log("EXITING", "init=" + InitDone);
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
}
