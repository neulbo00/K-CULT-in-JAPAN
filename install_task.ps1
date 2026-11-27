$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "K-CULT Notion Daily Sync"
$Bat = Join-Path $Project "sync.bat"
$Quote = [char]34
$Action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\cmd.exe" -Argument ("/c " + $Quote + $Bat + $Quote) -WorkingDirectory $Project
$Trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Daily Notion to K-CULT sync at 06:00" -Force | Out-Null
Write-Host "Registered daily 06:00 task: $TaskName"
