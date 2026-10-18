///----------------------------------------------------------------------------
///   DonationAlerts live spike B. Throwaway Phase 1 probe, not product code.
///   Behavior is NOT verified live until docs/live-spikes/FINDINGS.md says so.
///   Second code sub-action: answers whether a named semaphore, a global
///   variable and AppDomain data are shared with spike A (cross-AppDomain probes).
///   Every log line: SPIKE <A|B> <8-hex instance id> <MARKER> <details>.
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
    private const string Code = "B";
    private const string TraceFileName = "da-spike-trace.log";
    private const string OwnerSemaphoreName = @"Local\StreamerBot.DaSpike.Owner";
    private const string OwnerGlobalName = "daSpikeOwnerGen";
    private const string DomainDataKey = "daSpikeProbe";

    private readonly object traceLock = new object();

    private string InstanceId { get; set; } = Guid.NewGuid().ToString("N").Substring(0, 8);
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

    private void Log(string marker, string details)
    {
        string line = "SPIKE " + Code + " " + InstanceId + " " + marker;
        if (!string.IsNullOrEmpty(details))
            line += " " + details;
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

    private string DomainName()
    {
        try
        {
            return AppDomain.CurrentDomain.FriendlyName;
        }
        catch (Exception)
        {
            return "unknown";
        }
    }

    private int ProcessId()
    {
        try
        {
            return Process.GetCurrentProcess().Id;
        }
        catch (Exception)
        {
            return -1;
        }
    }

    public void Init()
    {
        Log(
            "INIT",
            "domain=" + AppDomain.CurrentDomain.Id
            + " domainName=" + DomainName()
            + " pid=" + ProcessId());
    }

    public void Dispose()
    {
        try
        {
            Log("DISPOSE-BEGIN", string.Empty);
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
            Log("DISPOSE-END", string.Empty);
        }
        catch (Exception)
        {
            // Dispose must never throw
        }
    }

    public bool SpikeBInfo()
    {
        try
        {
            Log(
                "INFO",
                "domain=" + AppDomain.CurrentDomain.Id
                + " domainName=" + DomainName()
                + " pid=" + ProcessId());
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBInfo", ex);
            return false;
        }
    }

    public bool SpikeBOwnSemTry()
    {
        try
        {
            bool createdNew;
            OwnerSemaphore = new Semaphore(1, 1, OwnerSemaphoreName, out createdNew);
            OwnerHeld = OwnerSemaphore.WaitOne(0);
            Log("OWN-SEM", "acquired=" + OwnerHeld + " createdNew=" + createdNew);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBOwnSemTry", ex);
            return false;
        }
    }

    public bool SpikeBOwnSemRelease()
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
            Log("OWN-SEM", "released=" + released);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBOwnSemRelease", ex);
            return false;
        }
    }

    public bool SpikeBOwnGenCheck()
    {
        try
        {
            string seen = CPH.GetGlobalVar<string>(OwnerGlobalName, false);
            Log("OWN-GEN", "seen=" + (seen ?? string.Empty));
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBOwnGenCheck", ex);
            return false;
        }
    }

    public bool SpikeBOwnStatic()
    {
        try
        {
            object seen = AppDomain.CurrentDomain.GetData(DomainDataKey);
            Log(
                "OWN-STATIC",
                "seen=" + (seen == null ? "null" : Convert.ToString(seen, CultureInfo.InvariantCulture))
                + " domain=" + AppDomain.CurrentDomain.Id);
            return true;
        }
        catch (Exception ex)
        {
            LogFailure("SpikeBOwnStatic", ex);
            return false;
        }
    }

    public bool Execute()
    {
        return true;
    }
}
