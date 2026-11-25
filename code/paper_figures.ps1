$ErrorActionPreference='Stop'
$src='D:\Desktop\汇报\新建文件夹 (1)\20260917_143733_877999'
$base='D:\srdd\paper_build\assets'
$dest='D:\srdd\output\paper_figures'
$p1='Işıl et al., Science Advances 8, eadd3433 (2022), Figs. 1–6. https://doi.org/10.1126/sciadv.add3433'
$p2='Chen et al., Super-resolution image projection over an extended depth of field using a diffractive decoder, Light: Science & Applications 15, 236 (2026), Fig. 1.'
$p3='Duan et al., Multi-wavelength diffractive deep neural networks, Fig. 1; visual convention for channel identity only. Local reference: 多波长复用.pdf.'
$run='Local scalar run: 20260917_143733_877999; config.json, README.txt, history.csv, sample_metrics.json, test_metrics.json and saved arrays. No polarization term.'
function RGB([string]$h){[Convert]::ToInt32($h.Substring(0,2),16)+256*[Convert]::ToInt32($h.Substring(2,2),16)+65536*[Convert]::ToInt32($h.Substring(4,2),16)}
$ink=RGB '172E38';$mut=RGB '526771';$rule=RGB 'CDD9DD';$pale=RGB 'F0F5F6';$teal=RGB '147869';$blue=RGB '117DA9';$orange=RGB 'BC5C2C';$purple=RGB '7657A0';$gray=RGB '9CABB0'
function T($str,$x,$y,$w,$h,$s=16,$c=$ink,$b=$false,$align=1){
  $o=$script:slide.Shapes.AddTextbox(1,$x,$y,$w,$h)
  $f=$o.TextFrame;$f.MarginLeft=0;$f.MarginRight=0;$f.MarginTop=0;$f.MarginBottom=0;$f.WordWrap=-1
  $t=$f.TextRange;$t.Text=$str;$t.Font.Name='Arial';$t.Font.Size=[single]$s;$t.Font.Color.RGB=[int]$c
  $t.Font.Bold=$(if($b){-1}else{0});$t.ParagraphFormat.Alignment=$align
}
function L($x1,$y1,$x2,$y2,$c=$rule,$weight=1,$arrow=$false){
  $q=$script:slide.Shapes.AddLine($x1,$y1,$x2,$y2);$q.Line.ForeColor.RGB=[int]$c;$q.Line.Weight=[single]$weight
  if($arrow){$q.Line.EndArrowheadStyle=3}
}
function Box($x,$y,$w,$h,$fill=$pale,$outline=$null){
  $q=$script:slide.Shapes.AddShape(1,$x,$y,$w,$h);$q.Fill.ForeColor.RGB=[int]$fill
  if($null -eq $outline){$q.Line.Visible=0}else{$q.Line.ForeColor.RGB=[int]$outline}
}
function P($path,$x,$y,$w,$h){[void]$script:slide.Shapes.AddPicture($path,0,-1,$x,$y,$w,$h)}
function ImageSquare($name,$x,$y,$size){P (Join-Path $base ($name+'.png')) $x $y $size $size}
function Panel($label,$name,$x,$y,$w=400){
  T $label $x $y 24 24 18 $teal $true
  T $name ($x+28) $y ($w-28) 25 17 $ink $true
}
function Figure($n,$title,$sub){
  $script:slide=$deck.Slides.Add($n,12)
  $script:slide.FollowMasterBackground=0;$script:slide.Background.Fill.ForeColor.RGB=16777215
  T ('FIGURE 0'+$n) 34 25 105 18 12 $teal $true
  T $title 34 45 892 40 29 $ink $true
  T $sub 35 88 890 26 14 $mut
  L 35 122 925 122 $rule 1
}
function Foot($msg,$notes){
  L 35 574 925 574 $rule 1
  T $msg 35 584 890 25 12 $mut
  $script:slide.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text=$notes
}
function Legend($str,$x,$y,$c){
 L $x ($y+8) ($x+22) ($y+8) $c 2.3
 T $str ($x+28) $y 182 20 12 $mut
}
function Axes($x,$y,$w,$h,$yt,$xt,$ticks){
 for($i=0;$i -lt $ticks.Count;$i++){
  $z=$y+$h-$i*$h/($ticks.Count-1)
  L $x $z ($x+$w) $z $rule 0.65
  T ([string]$ticks[$i]) ($x-39) ($z-8) 32 16 10 $mut $false 3
 }
 L $x $y $x ($y+$h) $ink 0.85
 L $x ($y+$h) ($x+$w) ($y+$h) $ink 0.85
 T $yt ($x-6) ($y-24) ($w+30) 20 12 $mut
 T $xt ($x+20) ($y+$h+18) ($w-40) 17 11 $mut $false 2
}
function Trace($values,$x,$y,$w,$h,$lo,$hi,$c,$step=$false){
 for($i=1;$i -lt $values.Count;$i++){
   $a=$x+($i-1)*$w/($values.Count-1);$b=$x+$i*$w/($values.Count-1)
   $u=$y+$h*(1-([double]$values[$i-1]-$lo)/($hi-$lo))
   $v=$y+$h*(1-([double]$values[$i]-$lo)/($hi-$lo))
   if($step){L $a $u $b $u $c 1.7; if([math]::Abs($u-$v) -gt 0.001){L $b $u $b $v $c 1.7}}
   else{L $a $u $b $v $c 1.8}
 }
}
$app=New-Object -ComObject PowerPoint.Application
$alerts=$app.DisplayAlerts
$app.DisplayAlerts=1
$deck=$null
try{
 $deck=$app.Presentations.Add(0)
 $deck.PageSetup.SlideWidth=960;$deck.PageSetup.SlideHeight=620

 Figure 1 'Dual-channel polarization pixel super-resolution' 'Proposed architecture  |  One 24 × 24 phase code for two 96 × 96 image targets'
 Panel 'a' 'Electronic encoding and polarization readout' 35 138 680
 ImageSquare '7_target' 54 186 62; ImageSquare '2_target' 122 186 62
 L 54 252 116 252 $blue 2; L 122 252 184 252 $orange 2
 T 'Two targets' 54 263 130 19 13 $ink $true 2
 L 192 218 224 218 $ink 1.8 $true
 Box 230 187 122 62 $pale $rule;T "Electronic`nencoder" 238 199 106 42 15 $ink $true 2
 L 360 218 389 218 $ink 1.8 $true
 ImageSquare '7_phase' 397 184 68
 T 'Phase code (example)' 368 262 126 21 13 $ink $true 2
 L 473 218 505 218 $teal 2 $true
 foreach($i in 0..2){Box (514+37*$i) 188 27 59 (RGB 'EEE7F5') $purple;T ('J'+($i+1)) (514+37*$i) 207 27 20 13 $purple $true 2}
 T 'Three optical stages' 494 262 148 20 13 $ink $true 2
 L 622 218 657 218 $teal 2 $true
 Box 664 188 99 60 $pale $rule;T "QWP + PBS`nreadout" 671 198 85 42 14 $ink $true 2
 L 768 218 787 218 $teal 2;L 787 191 787 244 $teal 1.6
 L 787 191 813 191 $blue 2 $true;L 787 244 813 244 $orange 2 $true
 T "LCP · image A`n96 × 96" 821 174 100 41 13 $blue $true
 T "RCP · image B`n96 × 96" 821 227 100 41 13 $orange $true
 L 35 297 925 297
 Panel 'b' 'Folded reflective implementation' 35 311 530
 P 'D:\srdd\models\figure\apparatus.png' 38 344 700 210
 L 642 357 642 544 $rule
 T 'Optical sequence' 669 351 235 25 16 $ink $true
 T "Laser and polarization preparation`n↓`nReflective encoding SLM`n↓`nThree reflective LCOS devices`n↓`nCircular analysis and two detectors" 669 381 246 152 15 $mut
 Foot 'Concept schematic. Image and phase tiles illustrate format; optical layout is not to scale.' "$p1`n$p2`n$p3`nApparatus: original Blender scene from this project. Target and phase tiles: scalar run, used only to illustrate tensor dimensions; not a shared dual-channel code."

 Figure 2 'Polarization coupling in the three-stage decoder' 'Effective Jones model in the circular basis; commercial LCOS response requires calibration'
 Panel 'a' 'Coupling at one liquid-crystal stage' 35 140 480
 T 'E = [Eᴸ, Eᴿ]ᵀ' 52 189 300 32 22 $ink $true
 Box 52 235 398 121 (RGB 'F4EFF8')
 T 'J(θ, Γ) =' 68 270 99 32 20 $purple $true
 L 167 252 167 334 $purple 1.5;L 167 252 176 252 $purple 1.5;L 167 334 176 334 $purple 1.5
 L 430 252 430 334 $purple 1.5;L 421 252 430 252 $purple 1.5;L 421 334 430 334 $purple 1.5
 T 'c' 188 261 103 22 18 $blue $true 2
 T '−i s exp(−i2θ)' 300 261 119 24 16 $purple $false 2
 T '−i s exp(+i2θ)' 178 305 119 24 16 $purple $false 2
 T 'c' 303 304 103 22 18 $orange $true 2
 T 'c = cos(Γ/2)     s = sin(Γ/2)' 57 371 393 24 17 $ink
 T 'θ: local optical-axis angle' 57 411 390 23 15 $mut
 T 'Γ: phase retardance' 57 438 390 23 15 $mut
 T 'L = (1, i) / √2; R = (1, −i) / √2' 57 475 391 23 15 $mut
 L 477 153 477 520
 Panel 'b' 'Ideal single-stage power fractions' 505 140 420
 Legend 'Preserved: cos²(Γ/2)' 533 179 $blue; Legend 'Converted: sin²(Γ/2)' 719 179 $orange
 Axes 565 242 319 196 'Power fraction' 'Retardance Γ / π' @('0','0.25','0.50','0.75','1')
 $v1=@();$v2=@();foreach($k in 0..32){$v1+= [math]::Pow([math]::Cos([math]::PI*$k/64),2);$v2+=1-$v1[-1]}
 Trace $v1 565 242 319 196 0 1 $blue
 Trace $v2 565 242 319 196 0 1 $orange
 foreach($i in 0..4){T ([string]($i/4)) (552+$i*79.75) 443 26 14 10 $mut $false 2}
 L 628.8 243 628.8 437 $purple 0.8
 T 'Γ = π/5: 90.5% preserved, 9.5% converted' 510 496 407 25 15 $purple $true
 T 'Three stages act on the coupled complex field before intensity readout.' 51 532 860 24 15 $ink $true
 Foot 'Curves are analytic for a lossless retarder, not measured LCOS transfer curves.' "Local 偏振调制演化推导.pdf, equations (26)–(28). Γ=π/5 is the reference value in 双通道偏振调制.txt. Power fractions are analytic, not device data. $p3"

 Figure 3 'Single-channel reconstruction examples' 'Scalar simulation baseline  |  Three learned phase layers  |  Five saved MNIST test cases'
 $digits=@(7,2,1,6,8);$ids=@(0,1,2,11,61)
 $metrics=Get-Content -LiteralPath (Join-Path $src 'sample_metrics.json') -Raw | ConvertFrom-Json
 $rows=@('Target image','Encoded phase','Scalar reconstruction','Sampling baseline')
 $dims=@('96 × 96','24 × 24 · 0 to 2π','96 × 96 · flux normalized','4 × 4 block average')
 $tags=@('target','phase','rec','lr')
 for($i=0;$i -lt 5;$i++){
  $x=255+126*$i
  T ('Test index '+$ids[$i]) ($x-15) 137 110 19 12 $mut $true 2
  for($j=0;$j -lt 4;$j++){ImageSquare ($digits[$i].ToString()+'_'+$tags[$j]) $x (159+95*$j) 78}
  $m=$metrics|Where-Object {$_.test_index -eq $ids[$i]}
  T ('{0:F2} dB' -f [double]$m.psnr_db) ($x-13) 427 104 17 11 $teal $true 2
 }
 for($j=0;$j -lt 4;$j++){
  $y=181+95*$j
  Panel ([string][char](97+$j)) $rows[$j] 37 $y 214
  T $dims[$j] 65 ($y+25) 180 19 12 $mut
 }
 T 'Phase' 36 544 42 16 11 $mut
 for($i=0;$i -lt 16;$i++){$v=[int]($i*17); Box (80+$i*7) 546 7 7 ($v*65793)}
 T '0' 80 555 13 14 9 $mut;T '2π' 181 555 22 14 9 $mut
 T 'Intensity tiles displayed on a common [0, 1] scale.' 250 544 650 20 12 $mut
 Foot 'Single-channel simulation only. The intensity baseline is a block-average reference, not a second polarization channel.' "$p1`n$run`nExamples assembled from exact target, wrapped phase and flux-normalized reconstruction arrays; preview intensities clipped to [0,1]. Baseline computed by 4×4 block averaging, displayed with nearest-neighbor scaling. PSNR values from sample_metrics.json."

 Figure 4 'Scalar baseline: convergence and learned phase maps' '20 epochs at 520 nm  |  200 × 200 samples per decoder layer  |  No polarization term'
 Panel 'a' 'Training and validation loss' 35 139 440
 Panel 'b' 'Validation PSNR' 505 139 416
 $data=Import-Csv -LiteralPath (Join-Path $src 'history.csv')
 $train=@($data|ForEach-Object {[double]$_.train_loss});$val=@($data|ForEach-Object {[double]$_.val_loss});$psnr=@($data|ForEach-Object {[double]$_.val_psnr_db})
 Legend 'Training' 91 172 $teal;Legend 'Validation' 257 172 $purple
 Axes 89 218 348 135 'Normalized MAE' 'Epoch' @('0.00','0.03','0.06','0.09','0.12')
 Axes 556 218 348 135 'PSNR (dB)' 'Epoch' @('16','19','22','25','28')
 Trace $train 89 218 348 135 0 .12 $teal;Trace $val 89 218 348 135 0 .12 $purple
 Trace $psnr 556 218 348 135 16 28 $blue
 foreach($n in @(1,5,10,15,20)){
   $x=348*($n-1)/19
   T ([string]$n) (79+$x) 355 20 14 10 $mut $false 2
   T ([string]$n) (546+$x) 355 20 14 10 $mut $false 2
 }
 L 35 401 925 401
 Panel 'c' 'Learned phase maps' 35 412 495
 Panel 'd' 'Held-out test set' 551 412 355
 for($i=1;$i -le 3;$i++){
   $x=67+139*($i-1)
   P (Join-Path $src ('decoder_layer_'+$i+'_200x200_gray.png')) $x 443 94 94
   T ('Layer '+$i) $x 542 94 18 12 $mut $false 2
 }
 for($i=0;$i -lt 16;$i++){$v=[int]($i*17); Box 492 (443+5.85*$i) 7 5.9 ((255-$v)*65793)}
 T '2π' 504 441 22 15 10 $mut;T '0' 504 525 22 15 10 $mut
 $m=Get-Content -LiteralPath (Join-Path $src 'test_metrics.json') -Raw | ConvertFrom-Json
 T ('{0:F2} dB' -f [double]$m.mean_psnr_db) 580 449 280 43 33 $teal $true
 T ('Mean PSNR · {0:N0} test samples' -f [int]$m.sample_count) 582 490 330 20 15 $ink $true
 T ('MSE {0:F5}  |  Pout / Pin {1:F3}%' -f [double]$m.mse,(100*[double]$m.efficiency_fraction)) 582 522 330 24 14 $mut
 Foot 'PSNR uses target-flux normalization. Test metrics are from the validation-selected epoch 20.' "$p1`n$run`nTrain and validation histories are actual CSV values. PSNR is the mean of per-sample values; efficiency is optical output/input power as defined by the scalar simulator, not wall-plug efficiency. Grayscale phase maps show wrapped phase in [0,2π]."

 Figure 5 'Resolution and polarization crosstalk tests' 'Proposed validation  |  Same field of view for targets, baselines and optical readout'
 Panel 'a' 'Independent line-pair targets' 35 140 458
 Panel 'b' 'Cross-section through vertical bars' 505 140 420
 T 'Target · 96 × 96' 126 176 126 18 12 $mut $true 2
 T 'Block average · 24 × 24' 265 176 166 18 12 $mut $true 2
 T 'Vertical' 44 235 76 22 13 $mut
 T 'Horizontal' 44 337 76 22 13 $mut
 ImageSquare 'v_fine' 145 201 88; ImageSquare 'v_coarse' 306 201 88
 ImageSquare 'h_fine' 145 302 88; ImageSquare 'h_coarse' 306 302 88
 Legend 'Target' 548 181 $blue; Legend 'Block average' 727 181 $orange
 Axes 561 230 326 130 'Normalized intensity' 'Position (fine-grid samples)' @('0','0.5','1.0')
 $pro=Get-Content -LiteralPath (Join-Path $base 'profiles.json') -Raw | ConvertFrom-Json
 Trace $pro.target 561 230 326 130 0 1 $blue $true
 Trace $pro.coarse 561 230 326 130 0 1 $orange $true
 foreach($i in @(0,8,16,23)){T ([string]$i) (551+326*$i/23) 362 20 15 10 $mut $false 2}
 L 35 412 925 412
 Panel 'c' 'Two one-target-at-a-time controls' 35 425 465
 T 'Input pair' 66 461 136 21 13 $mut $true
 T 'L detector' 219 461 110 21 13 $blue $true
 T 'R detector' 337 461 110 21 13 $orange $true
 L 66 481 453 481
 T 'A only · B = 0' 66 488 142 21 13 $ink
 T 'Desired' 219 488 110 21 13 $blue
 T 'Leakage' 337 488 110 21 13 $orange
 T 'B only · A = 0' 66 516 142 21 13 $ink
 T 'Leakage' 219 516 110 21 13 $blue
 T 'Desired' 337 516 110 21 13 $orange
 Panel 'd' 'Readouts to report' 505 425 420
 T "Resolution: line-pair contrast vs. spatial frequency`nCrosstalk: 10 log₁₀(P leakage / P desired), in dB`nUse dark-subtracted power under matched exposure." 532 465 389 85 15 $ink
 Foot 'Only synthetic targets and their sampling baseline are plotted. Optical response and crosstalk remain to be measured.' "$p1`nFigure 4 of the cited paper motivates unseen horizontal and vertical targets and transverse profiles. Fig. 5 here is a proposed protocol. Ideal line pairs have width and gap of two fine-grid samples, no physical calibration assigned. Profiles use exact target and 4×4 block-average values. Dual-channel test: apply the trained encoder to (A,0) and (0,B) and dark-subtract identical signal ROI power from each output."

 $deck.SaveAs((Join-Path $dest 'dual_polarization_paper_figures.pptx'),24)
 for($n=1;$n -le 5;$n++){$deck.Slides.Item($n).Export((Join-Path $dest ('Fig'+$n+'.png')),'PNG',3840,2480)}
 Write-Output ('EXPORTED '+$deck.Slides.Count+' figures')
}finally{
 if($null -ne $deck){$deck.Close()}
 $app.DisplayAlerts=$alerts
 [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}



