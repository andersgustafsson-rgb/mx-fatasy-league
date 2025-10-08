@echo off
echo Copying remaining track map images...

copy "static\trackmaps\2026\*_Rd08_*" "static\trackmaps\compressed\daytona.jpg"
copy "static\trackmaps\2026\*_Rd09_*" "static\trackmaps\compressed\indianapolis.jpg"
copy "static\trackmaps\2026\*_Rd10_*" "static\trackmaps\compressed\birmingham.jpg"
copy "static\trackmaps\2026\*_Rd11_*" "static\trackmaps\compressed\detroit.jpg"
copy "static\trackmaps\2026\*_Rd12_*" "static\trackmaps\compressed\stlouis.jpg"
copy "static\trackmaps\2026\*_Rd13_*" "static\trackmaps\compressed\nashville.jpg"
copy "static\trackmaps\2026\*_Rd14_*" "static\trackmaps\compressed\cleveland.jpg"
copy "static\trackmaps\2026\*_Rd15_*" "static\trackmaps\compressed\philadelphia.jpg"
copy "static\trackmaps\2026\*_Rd16_*" "static\trackmaps\compressed\denver.jpg"
copy "static\trackmaps\2026\*_Rd17_*" "static\trackmaps\compressed\saltlakecity.jpg"

echo Done!
pause
