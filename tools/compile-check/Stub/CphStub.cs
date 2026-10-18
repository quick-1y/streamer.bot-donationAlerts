using System;
using System.Collections.Generic;

///----------------------------------------------------------------------------
///   Dev-only CPH stub for the offline compile gate. NEVER shipped in a .sb.
///   Signatures were reflected from Streamer.bot 1.0.7
///   (Streamer.bot.Plugin.Interface.dll). Only the members this project uses
///   are declared; re-check with tools/verify-stub.ps1 after Streamer.bot updates.
///----------------------------------------------------------------------------
public interface IInlineInvokeProxy
{
    bool RegisterCustomTrigger(string triggerName, string eventName, string[] categories);
    void TriggerCodeEvent(string eventName, bool useArgs = true);
    void TriggerCodeEvent(string eventName, Dictionary<string, object> args);
    void TriggerCodeEvent(string eventName, string json);
    T GetGlobalVar<T>(string varName, bool persisted = true);
    void SetGlobalVar(string varName, object value, bool persisted = true);
    void UnsetGlobalVar(string varName, bool persisted = true);
    bool ExecuteMethod(string executeCode, string methodName);
    string GetVersion();
    bool TryGetArg<T>(string argName, out T value);
    void SetArgument(string variableName, object value);
    bool RunAction(string actionName, bool runImmediately = true);
    bool ActionExists(string actionName);
    void LogInfo(string logLine);
    void LogWarn(string logLine);
    void LogError(string logLine);
    void LogDebug(string logLine);
    void LogVerbose(string logLine);
    void Wait(int milliseconds);
}

[Serializable]
public class CPHInlineBase
{
    public IInlineInvokeProxy CPH { get { return null; } }
    public Dictionary<string, object> args { get { return null; } }

    public virtual void Init()
    {
    }

    public virtual void Dispose()
    {
    }

    public virtual bool Execute()
    {
        return true;
    }
}
