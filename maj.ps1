# Mise à jour de Saisio — Windows
#
#   .\maj.ps1
#
# Retélécharge la dernière version du code et la pose par-dessus l'installation
# existante. Ce qui vous appartient n'est jamais touché :
#   - saisio.env      (vos réglages et vos secrets) n'est pas dans le
#                     téléchargement, il reste donc en place ;
#   - les manifestes  (~/.saisio) vivent hors du projet, pour qu'une mise à jour
#                     ne fasse pas repayer l'OCR de tout l'historique ;
#   - la connexion    Google (~/.saisio/jeton_google.json) reste en place, vous
#                     n'avez pas à vous reconnecter.
#
# Le script s'arrête au premier problème plutôt que de laisser une installation
# à moitié remplacée.

$ErrorActionPreference = "Stop"

$Branche = "claude/s2a-intelligent-prototype-uv1peq"
$Zip     = "https://github.com/familleleguayetjoy-collab/LMNP/archive/refs/heads/$Branche.zip"
$Projet  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Temp    = Join-Path $env:TEMP ("saisio-maj-" + [guid]::NewGuid().ToString("N"))

Write-Host "Mise a jour de Saisio dans $Projet" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $Projet "tool\verifier_branchement.py"))) {
  Write-Host "Ce dossier ne ressemble pas a une installation de Saisio." -ForegroundColor Red
  Write-Host "Lancez maj.ps1 depuis le dossier du projet." -ForegroundColor Yellow
  exit 1
}

try {
  New-Item -ItemType Directory -Force -Path $Temp | Out-Null
  $Archive = Join-Path $Temp "saisio.zip"

  Write-Host "  telechargement..."
  Invoke-WebRequest $Zip -OutFile $Archive

  Write-Host "  decompression..."
  Expand-Archive $Archive -DestinationPath $Temp -Force

  $Source = Get-ChildItem $Temp -Directory | Select-Object -First 1
  if (-not $Source) { throw "archive vide ou illisible" }

  # Un fichier a la fois, par-dessus : rien n'est supprime, donc saisio.env et
  # tout ce que vous avez pu deposer dans le dossier survivent.
  Write-Host "  installation..."
  Copy-Item (Join-Path $Source.FullName "*") $Projet -Recurse -Force

  Write-Host "Mise a jour terminee." -ForegroundColor Green
  Write-Host "Verifiez avec :  python tool\verifier_branchement.py --etape moteur"
}
finally {
  if (Test-Path $Temp) { Remove-Item $Temp -Recurse -Force -ErrorAction SilentlyContinue }
}
