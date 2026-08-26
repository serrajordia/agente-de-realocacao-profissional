# Cria/atualiza a tarefa agendada "AgenteRecolocacao" no Windows Task Scheduler.
# Roda `python main.py` toda segunda e quarta, no horário definido abaixo.

$TaskName = "AgenteRecolocacao"
$RunTime = "07:00"
$RunDays = "Monday", "Wednesday"
$ProjectDir = $PSScriptRoot
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$MainScript = Join-Path $ProjectDir "main.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "python.exe nao encontrado em $PythonExe. Ajuste a variavel `$PythonExe neste script."
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$MainScript`"" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $RunDays -At $RunTime
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Agente de recolocacao: busca e classifica vagas, envia resumo por e-mail e sobe resultados no Drive." `
    -Force

Write-Output "Tarefa '$TaskName' criada/atualizada: roda segunda e quarta as $RunTime."
