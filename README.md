# cooking_content_creator_multiagent
A cooking related content creator multiagent

## Done:
- ✅Define ContentState
- ✅Build graph structure
- ✅Verify interrupt_before
- ✅Build Trend Agent
- ✅Test Trend Agent
- ✅Build Recipe node
- ✅Test Recipe node
- ✅Build Content node
- ✅Test Content node
- ✅Build Image Agent
- ✅Test Image Agent

## In process:
- ⌨️Build Publisher Agent
- ⌨️Test Publisher Agent

## Next steps:
- 🔜Build Orchestrator Agent
- 🔜Test Orchestrator Agent
- 🔜Test full workflow (with working human review)
- 🔜Polish + final touches
- 🔜Clean README of the hole project

## Future improvements:
- ✨Error Agent


### How to make it work (Windows)
```
python3.11 -m venv venv
venv/Scripts/activate
pip install -r requirements.txt
```

Load .env variables (In powershell):
```
Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]*)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}
```