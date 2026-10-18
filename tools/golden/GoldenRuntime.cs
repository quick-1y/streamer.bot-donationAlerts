using System;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

#if EXTERNAL_EDITOR
public class CPHInline : CPHInlineBase
#else
public class CPHInline
#endif
{
    public void Init()
    {
        bool registered = CPH.RegisterCustomTrigger("Golden: Event", "goldenEvent", new[] { "Golden" });
        CPH.LogInfo("GOLDEN INIT registered=" + registered);
    }

    public bool GoldenPing()
    {
        var probe = new Dictionary<string, object>();
        probe["ping"] = 1;
        CPH.LogInfo("GOLDEN PING " + JsonConvert.SerializeObject(probe) + " http=" + typeof(HttpClient).Name);
        return true;
    }

    public bool GoldenFire()
    {
        var args = new Dictionary<string, object>();
        args["spikeAmount"] = 22.5m;
        args["spikeCount"] = 7;
        args["spikeFlag"] = true;
        args["spikeText"] = "x";
        CPH.TriggerCodeEvent("goldenEvent", args);
        CPH.LogInfo("GOLDEN FIRE");
        return true;
    }

    public bool Execute()
    {
        return true;
    }

    public void Dispose()
    {
        try
        {
            CPH.LogInfo("GOLDEN DISPOSE");
        }
        catch (Exception)
        {
        }
    }
}
