$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root 'output\paper_figures_v2'
$assets = Join-Path $root 'paper_build\assets'
$revision = Join-Path $root 'paper_build\revision_assets'
$src = 'D:\Desktop\汇报\新建文件夹 (1)\20260917_143733_877999'
New-Item -ItemType Directory -Path $dest -Force | Out-Null

# Share the existing PowerPoint drawing helpers, without executing the previous deck.
$previous = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'paper_figures.ps1') -Raw
$first = $previous.IndexOf('function RGB')
$last = $previous.IndexOf('$app=New-Object')
. ([scriptblock]::Create($previous.Substring($first, $last - $first)))
$base = $assets
$teal = RGB '20745B'
$blue = RGB '126F98'
$orange = RGB 'B65328'
$purple = RGB '694D94'
$softblue = RGB 'EAF4F8'
$softorange = RGB 'FCF0E8'
$softpurple = RGB 'F2EDF8'
$softgreen = RGB 'EDF6EF'
$neutral = RGB 'F4F6F7'
$white = RGB 'FFFFFF'

function Tile($name,$x,$y,$size) { ImageSquare $name $x $y $size }
function Caption($msg,$x,$y,$w,$color=$mut,$weight=$false) {
  T $msg $x $y $w 20 12 $color $weight 2
}
function Pending($title,$x,$y,$w,$h,$shade=$neutral,$color=$mut) {
  Box $x $y $w $h $shade $rule
  T $title ($x+4) ($y+($h-22)/2) ($w-8) 24 11 $color $false 2
}
function Link($x1,$y1,$x2,$y2,$color=$teal) { L $x1 $y1 $x2 $y2 $color 1.65 $true }
function Circle($x,$y,$d,$fill,$edge) {
  $q=$script:slide.Shapes.AddShape(9,$x,$y,$d,$d)
  $q.Fill.ForeColor.RGB=[int]$fill
  $q.Line.ForeColor.RGB=[int]$edge
}
function Mark($n,$x,$y) {
  Circle ($x-9) ($y-9) 18 $white $ink
  T $n ($x-8) ($y-7) 16 16 11 $ink $true 2
}
function Device($tag,$x,$y,$w,$shade,$color) {
  Box $x $y $w 36 $shade $color
  T $tag ($x+3) ($y+9) ($w-6) 22 12 $color $true 2
}

$fu='Fu et al., Optics and Lasers in Engineering (2026), Figs. 1–2. DOI 10.1016/j.optlaseng.2026.109800.'
$snapshot='Işıl et al., Light: Science & Applications 15, 270 (2026). DOI 10.1038/s41377-026-02378-3.'
$sci='Işıl et al., Science Advances 8, eadd3433 (2022), Fig. 4. DOI 10.1126/sciadv.add3433.'
$scalar='Local 520 nm single-channel scalar simulation, run 20260917_143733_877999.'
$app=New-Object -ComObject PowerPoint.Application
$alerts=$app.DisplayAlerts
$app.DisplayAlerts=1
$deck=$null
try {
  $deck=$app.Presentations.Add(0)
  $deck.PageSetup.SlideWidth=960
  $deck.PageSetup.SlideHeight=620

  Figure 1 'Dual-channel polarization imaging' 'Proposed pixel super-resolution architecture  |  532 nm illumination'
  Panel 'a' 'Joint electronic encoding and optical reconstruction' 35 137 865
  Caption '96 × 96 targets' 41 170 92 $ink $true
  Tile '7_target' 58 194 56
  Tile '2_target' 58 256 56
  Caption 'A' 37 214 19 $blue $true
  Caption 'B' 37 276 19 $orange $true
  L 115 222 132 222 $blue 1.5
  L 115 284 132 284 $orange 1.5
  L 132 222 132 284 $ink 1.1
  Link 132 253 158 253 $ink
  Box 162 220 107 67 $neutral $rule
  T "Electronic`nencoder" 168 231 95 43 16 $ink $true 2
  Link 272 253 309 253 $ink
  Tile '7_phase' 315 218 70
  Caption '24 × 24 phase code' 290 294 120 $ink $true
  Link 390 253 428 253
  foreach($idx in 0..2) {
    $x=434+48*$idx
    Box $x 216 28 74 $softpurple $purple
    T ('J'+($idx+1)) ($x+1) 240 26 27 17 $purple $true 2
    if($idx -lt 2){ Link ($x+29) 253 ($x+45) 253 }
  }
  Caption 'Three LCOS stages' 420 294 150 $ink $true
  Link 559 253 598 253
  Box 602 220 112 67 $softgreen $teal
  T "Circular analysis`nQWP + PBS" 606 233 104 40 13 $teal $true 2
  L 716 253 755 253 $teal 1.6
  L 755 220 755 286 $teal 1.4
  Link 755 220 788 220 $blue
  Link 755 286 788 286 $orange
  Pending 'Image A' 794 196 61 47 $softblue $blue
  Pending 'Image B' 794 263 61 47 $softorange $orange
  T "LCP`n96 × 96" 865 200 60 43 13 $blue $true
  T "RCP`n96 × 96" 865 268 60 43 13 $orange $true
  L 35 328 925 328
  Panel 'b' 'Effective Jones coupling at one stage' 35 343 520
  T 'Eout = Jₖ Ein' 52 375 136 28 20 $ink $true
  L 188 384 188 457 $purple 1.4
  L 188 384 196 384 $purple 1.4
  L 188 457 196 457 $purple 1.4
  L 460 384 460 457 $purple 1.4
  L 452 384 460 384 $purple 1.4
  L 452 457 460 457 $purple 1.4
  T 'Jₖ =' 125 408 58 27 20 $purple $true
  T 'c' 201 392 119 24 17 $blue $true 2
  T '−i s exp(+iβₖ)' 329 392 122 24 15 $purple $false 2
  T '−i s exp(−iβₖ)' 199 427 124 24 15 $purple $false 2
  T 'c' 330 427 119 24 17 $orange $true 2
  T 'c = cos(Γ/2),  s = sin(Γ/2),  βₖ = 2θₖ' 52 475 415 24 15 $ink
  T 'Complex field order [Eᴸ, Eᴿ]ᵀ' 52 514 415 22 14 $mut
  L 481 361 481 551
  Panel 'c' 'Per-stage polarization paths' 511 343 409
  T 'L' 523 389 35 22 17 $blue $true
  T 'R' 523 455 35 22 17 $orange $true
  T 'L' 883 389 22 22 17 $blue $true
  T 'R' 883 455 22 22 17 $orange $true
  Link 558 401 869 401 $blue
  Link 558 467 869 467 $orange
  Link 587 402 839 466 $purple
  Link 587 466 839 402 $purple
  Caption 'Co-polarized amplitude c' 568 375 283 $mut
  Caption 'Cross-polarized amplitude −is with phase ±βₖ' 522 496 385 $purple
  T 'Each stage mixes the fields before intensity detection.' 522 532 386 23 13 $mut
  Foot 'Concept schematic. The phase tile illustrates the code format. Jones response is an effective model.' "$fu`nSnapshot Fig. 1 motivates division into encoder and decoder. Luo et al., Laser & Photonics Reviews (2023), Fig. 1b motivates the polarization inset. Effective Jones sign convention follows polar_sr_cuda.py. Code thumbnail is from the scalar run and illustrates format only."

  Figure 2 'Shared phase code and paired reconstructions' 'Paired result layout for LCP and RCP with a saved scalar benchmark'
  Panel 'a' 'Paired examples and low-resolution intensity references' 35 137 850
  $columns=@('LCP target','RCP target','Shared phase','LCP output','RCP output','A baseline','B baseline')
  $dims=@('96 × 96','96 × 96','24 × 24','96 × 96','96 × 96','24 × 24','24 × 24')
  $xs=@(103,218,333,448,563,678,793)
  for($j=0;$j -lt $xs.Count;$j++){
    Caption $columns[$j] ($xs[$j]-12) 173 103 $ink $true
    Caption $dims[$j] ($xs[$j]-10) 191 99
  }
  $pairs=@(@(7,2),@(1,8))
  for($r=0;$r -lt $pairs.Count;$r++){
    $a,$b=$pairs[$r]
    $y=211+97*$r
    T ('Pair '+($r+1)) 36 ($y+28) 66 21 13 $ink $true
    Tile "${a}_target" $xs[0] $y 79
    Tile "${b}_target" $xs[1] $y 79
    Pending 'Pending' $xs[2] $y 79 79 $softpurple $purple
    Pending 'Pending' $xs[3] $y 79 79 $softblue $blue
    Pending 'Pending' $xs[4] $y 79 79 $softorange $orange
    Tile "${a}_lr" $xs[5] $y 79
    Tile "${b}_lr" $xs[6] $y 79
  }
  L 35 408 925 408
  Panel 'b' 'Single-channel scalar benchmark' 35 423 470
  Panel 'c' 'Learned scalar decoder phases' 503 423 415
  $tags=@('target','phase','rec','lr')
  $labels=@('Target','24 × 24 code','Reconstruction','Block average')
  for($j=0;$j -lt 4;$j++){
    $x=55+104*$j
    Tile ('7_'+$tags[$j]) $x 454 74
    Caption $labels[$j] ($x-14) 535 102
  }
  for($j=1;$j -le 3;$j++){
    $x=539+103*($j-1)
    P (Join-Path $src ('decoder_layer_'+$j+'_200x200_gray.png')) $x 454 74 74
    Caption ('Layer '+$j) $x 535 74
  }
  for($j=0;$j -lt 16;$j++){Box 855 (455+$j*4.5) 9 4.6 ((255-17*$j)*65793)}
  T '2π' 871 451 30 19 11 $mut
  T '0' 871 513 30 19 11 $mut
  Foot 'Paired targets and intensity references are shown above. The 520 nm benchmark below uses one channel.' "$fu`n$snapshot`n$scalar`nPanel a uses independently paired reference targets; shared codes and optical outputs require a dual-channel run. Intensity references are 4 × 4 block averages. Panel b shows scalar test index 0 and c shows that scalar model's phases."

  Figure 3 'Reconstruction fidelity and optical efficiency' 'Quantification of the scalar benchmark and planned comparison for both circular channels'
  Panel 'a' 'Scalar training and validation loss' 35 138 455
  Panel 'b' 'Scalar validation PSNR' 495 138 425
  $data=Import-Csv -LiteralPath (Join-Path $src 'history.csv')
  $train=@($data|ForEach-Object {[double]$_.train_loss})
  $val=@($data|ForEach-Object {[double]$_.val_loss})
  $psnr=@($data|ForEach-Object {[double]$_.val_psnr_db})
  Legend 'Training' 85 169 $teal
  Legend 'Validation' 218 169 $purple
  Axes 87 218 344 118 'Normalized MAE' 'Epoch' @('0.00','0.03','0.06','0.09','0.12')
  Axes 544 218 344 118 'PSNR (dB)' 'Epoch' @('16','19','22','25','28')
  Trace $train 87 218 344 118 0 .12 $teal
  Trace $val 87 218 344 118 0 .12 $purple
  Trace $psnr 544 218 344 118 16 28 $blue
  foreach($n in @(1,5,10,15,20)){
    $dx=344*($n-1)/19
    Caption ([string]$n) (73+$dx) 337 28
    Caption ([string]$n) (530+$dx) 337 28
  }
  L 35 380 925 380
  Panel 'c' 'Held-out scalar benchmark' 35 393 420
  Panel 'd' 'Paired comparison to report' 476 393 449
  $summary=Get-Content -LiteralPath (Join-Path $src 'test_metrics.json') -Raw | ConvertFrom-Json
  T ('{0:F2} dB' -f [double]$summary.mean_psnr_db) 52 435 391 50 35 $teal $true
  T ('Mean PSNR across {0:N0} test images' -f [int]$summary.sample_count) 54 482 391 25 16 $ink $true
  T ('MSE {0:F5}    Pout / Pin {1:F3}%' -f [double]$summary.mse,(100*[double]$summary.efficiency_fraction)) 54 514 397 24 14 $mut
  Box 477 427 447 32 $neutral
  T 'Comparison' 489 435 205 23 13 $ink $true
  Caption 'LCP' 700 435 92 $blue $true
  Caption 'RCP' 815 435 92 $orange $true
  $conditions=@('Three LCOS stages','One LCOS stage')
  foreach($r in 0..1){
    $y=463+31*$r
    T $conditions[$r] 489 ($y+4) 200 20 13
    Caption 'Pending' 700 ($y+4) 92
    Caption 'Pending' 815 ($y+4) 92
    L 478 ($y+28) 922 ($y+28)
  }
  T 'Report PSNR, SSIM and ROI power / incident power.' 489 537 426 23 13 $mut
  Foot 'Curves and metrics use the 520 nm scalar run. The paired comparison requires 532 nm dual-channel results.' "$snapshot`nSnapshot Fig. 2b motivates reporting performance per output and comparing decoder configurations. $scalar`nPanels a–c use history.csv and test_metrics.json. Fig. 3d specifies the planned comparison; it contains no simulated or measured paired values."

  Figure 4 'Resolution and channel isolation' 'Validation design  |  Independent line targets and one-channel-at-a-time controls'
  Panel 'a' 'Line pairs at multiple separations' 35 137 440
  Panel 'b' 'Transverse profile at the smallest gap' 497 137 425
  $gaps=@(2,4,8)
  foreach($j in 0..2){
    $gap=$gaps[$j]
    $x=176+$j*85
    Caption ([string]$gap) $x 173 56 $ink $true
    P (Join-Path $revision ('vertical_'+$gap+'.png')) $x 198 56 56
    P (Join-Path $revision ('horizontal_'+$gap+'.png')) $x 261 56 56
    P (Join-Path $revision ('coarse_'+$gap+'.png')) $x 324 56 56
  }
  T 'Gap (samples)' 40 174 130 19 12 $mut $true
  T 'Vertical target' 40 218 130 19 13
  T 'Horizontal target' 40 281 130 19 13
  T "Vertical 24 × 24`nbaseline" 40 331 131 41 13
  Legend '96 × 96 target' 516 175 $blue
  Legend '24 × 24 block average' 705 175 $purple
  Axes 542 222 342 125 'Normalized intensity' 'Position (fine-grid samples)' @('0','0.5','1.0')
  $profile=(Get-Content -LiteralPath (Join-Path $revision 'profiles.json') -Raw | ConvertFrom-Json).'2'
  Trace $profile.target 542 222 342 125 0 1 $blue $true
  Trace $profile.coarse 542 222 342 125 0 1 $purple $true
  foreach($n in @(0,8,16,23)){Caption ([string]$n) (528+342*$n/23) 348 28}
  L 35 394 925 394
  Panel 'c' 'Polarization isolation controls' 35 408 445
  Panel 'd' 'Evaluation metrics' 500 408 420
  T 'Input targets' 48 445 141 21 13 $ink $true
  Caption 'LCP detector' 195 445 120 $blue $true
  Caption 'RCP detector' 331 445 120 $orange $true
  L 48 465 450 465
  T '(A, 0)' 49 474 132 20 14
  T '(0, B)' 49 507 132 20 14
  Box 197 470 116 27 $softblue
  Box 332 503 116 27 $softorange
  Caption 'Desired' 197 474 116 $blue $true
  Caption 'Leakage' 332 474 116 $mut
  Caption 'Leakage' 197 507 116 $mut
  Caption 'Desired' 332 507 116 $orange $true
  T 'Line-pair contrast = (Ipeak − Ivalley) / (Ipeak + Ivalley)' 511 444 419 23 14 $ink
  T 'Crosstalk = 10 log₁₀(Pleak / Pdesired)  [dB]' 511 481 419 23 15 $ink
  T 'Use matched exposure and subtract the dark signal.' 511 520 390 37 13 $mut
  Foot 'Plots show synthetic targets and their sampling reference. Optical contrast and crosstalk are pending.' "$sci`n$snapshot`nSnapshot Fig. 3 motivates using different bar orientations in different channels. Line pairs are two fine-grid samples wide with gaps of 2, 4, or 8 samples. Report physical periods after calibrating detector sampling."

  Figure 5 'Folded reflective optical setup' 'Proposed apparatus  |  532 nm source, phase encoder, three LCOS stages and polarization readout'
  Panel 'a' 'Blender render of proposed setup' 35 138 548
  Panel 'b' 'Optical path and detector assignment' 586 138 340
  P (Join-Path $revision 'apparatus_crop.png') 45 175 520 296
  Mark '1' 87 232
  Mark '2' 224 287
  Mark '3' 319 188
  Mark '4' 344 284
  Mark '5' 517 254
  Mark '6' 486 361
  Mark 'A' 551 425
  Mark 'B' 420 431
  L 576 170 576 466
  Device '1  Laser' 590 182 117 $softgreen $teal
  Device '2  Phase encoder' 775 182 142 $softpurple $purple
  Link 710 200 771 200
  Caption 'P + QWP' 704 178 72 $teal
  Link 847 221 847 241
  Device '3  LCOS 1' 775 245 142 $softpurple $purple
  Link 771 263 712 263
  Device '4  LCOS 2' 590 245 117 $softpurple $purple
  Link 648 284 648 304
  Device '5  LCOS 3' 590 308 117 $softpurple $purple
  Link 710 326 771 326
  Device '6  QWP + PBS' 775 308 142 $softgreen $teal
  L 847 346 847 372 $teal 1.7
  L 671 372 847 372 $blue 1.7
  Link 671 372 671 396 $blue
  Link 847 372 847 396 $orange
  Device 'A  LCP readout' 596 400 149 $softblue $blue
  Device 'B  RCP readout' 772 400 149 $softorange $orange
  T 'P: polarizer   QWP: quarter-wave plate' 591 447 329 20 12 $mut
  T 'PBS: polarizing beam splitter' 591 466 329 20 12 $mut
  L 35 488 925 488
  Panel 'c' 'Planned comparison for the same input pair' 35 502 895
  Box 64 532 233 30 $neutral
  Box 362 532 233 30 $neutral
  Box 660 532 233 30 $neutral
  Caption 'Target A and B' 64 538 233 $ink $true
  Caption 'Simulated LCP and RCP' 362 538 233 $ink $true
  Caption 'Measured LCP and RCP' 660 538 233 $ink $true
  Link 302 547 355 547 $ink
  Link 600 547 653 547 $ink
  Foot 'Blender model and proposed path are schematic. Branch colors identify readout channels at the same wavelength.' "$snapshot`nSnapshot Fig. 8b–d and Yu et al., Acta Optica Sinica 45, 1911005 (2025), Fig. 4 motivate matching labels across a path drawing and an apparatus view. Blender apparatus from models/figure/apparatus.png. Detector labels refer to the circular basis before the analyzing QWP."

  $deck.SaveAs((Join-Path $dest 'dual_polarization_paper_figures_v2.pptx'),24)
  for($n=1;$n -le 5;$n++){
    $deck.Slides.Item($n).Export((Join-Path $dest ('Fig'+$n+'.png')),'PNG',3840,2480)
  }
  Write-Output ('EXPORTED '+$deck.Slides.Count+' figures')
} finally {
  if($null -ne $deck){$deck.Close()}
  $app.DisplayAlerts=$alerts
  [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}
