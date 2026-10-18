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
        // HashCode and Span<T> are absent from the net48 reference assemblies (expected diagnostic: CS0246).
        HashCode hash = new HashCode();
        Span<int> window = new Span<int>(new int[2]);
        var payload = new Dictionary<string, object>();
        payload["daFixture"] = window.Length;
        CPH.LogInfo("fixture " + JsonConvert.SerializeObject(payload) + hash);
        return true;
    }
}
