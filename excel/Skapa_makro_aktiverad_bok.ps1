# Försöker öppna en Excel-arbetsbok och importera ModulTidrapport.bas, sedan spara som .xlsm.
# Kräver: Microsoft Excel installerad + ofta "Lita på åtkomst till VBA-projektsmodellen"
#   (Fil → Alternativ → Säkerhetscenter → Inställningar → Makroinställningar).
#
# Kör i mappen excel:
#   powershell -ExecutionPolicy Bypass -File .\Skapa_makro_aktiverad_bok.ps1 -Arbetsbok "C:\sökväg\min_fil.xlsx"
#
# Resultat: samma sökväg men filändelse .xlsm (original .xlsx lämnas orörd om du sparar till nytt namn).

param(
    [Parameter(Mandatory = $true, HelpMessage = "Full sökväg till .xlsx eller .xlsm")]
    [string]$Arbetsbok
)

$ErrorActionPreference = "Stop"
$bas = Join-Path $PSScriptRoot "ModulTidrapport.bas"
if (-not (Test-Path $bas)) {
    Write-Error "Hittar inte ModulTidrapport.bas i samma mapp som skriptet: $bas"
}
if (-not (Test-Path $Arbetsbok)) {
    Write-Error "Hittar inte arbetsboken: $Arbetsbok"
}

$out = [System.IO.Path]::ChangeExtension($Arbetsbok, ".xlsm")
if ($out -ieq $Arbetsbok) {
    $dir = [System.IO.Path]::GetDirectoryName($Arbetsbok)
    $name = [System.IO.Path]::GetFileNameWithoutExtension($Arbetsbok)
    $out = Join-Path $dir ($name + "_med_makro.xlsm")
}

Write-Host "Öppnar Excel..."
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    $wb = $excel.Workbooks.Open($Arbetsbok)
    Write-Host "Importerar VBA-modul..."
    $wb.VBProject.VBComponents.Import($bas)
    Write-Host "Sparar som: $out"
    # 52 = xlOpenXMLWorkbookMacroEnabled
    if (Test-Path $out) { Remove-Item $out -Force }
    $wb.SaveAs($out, 52)
    $wb.Close($false)
    Write-Host "Klart."
}
catch {
    Write-Error "Misslyckades (vanlig orsak: Excel tillåter inte VBProject). Använd i stället manuella stegen i LAS_MIG_FORST.txt. Detalj: $($_.Exception.Message)"
}
finally {
    $excel.Quit() | Out-Null
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
}
