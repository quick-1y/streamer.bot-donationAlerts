using System;
using System.Collections.Generic;
using Newtonsoft.Json;

#if EXTERNAL_EDITOR
public class CPHInline : CPHInlineBase
#else
public class CPHInline
#endif
{
    public bool Execute()
    {
        var payload = new Dictionary<string, object>();
        // Deliberate break: the next statement has no terminating semicolon (expected diagnostic: CS1002).
        payload["daFixture"] = 1
        CPH.LogInfo("fixture " + JsonConvert.SerializeObject(payload));
        return true;
    }
}
