$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing.Common

$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root 'output\paper_figures_direct'
$previous = [Drawing.Bitmap]::new((Join-Path $out 'Fig1_dual_polarization.png'))
$render = [Drawing.Bitmap]::new((Join-Path $root 'models\figure\apparatus.png'))
$canvas = [Drawing.Bitmap]::new($previous.Width,$previous.Height,[Drawing.Imaging.PixelFormat]::Format24bppRgb)
$graphics = [Drawing.Graphics]::FromImage($canvas)
$background = [Drawing.Color]::FromArgb(253,253,253)
$ink = [Drawing.Color]::FromArgb(24,29,32)
$leader = [Drawing.Color]::FromArgb(89,101,106)
$blue = [Drawing.Color]::FromArgb(15,103,152)
$orange = [Drawing.Color]::FromArgb(175,73,30)
$labelFont = [Drawing.Font]::new('Times New Roman',28,[Drawing.FontStyle]::Bold,[Drawing.GraphicsUnit]::Pixel)
$measureFont = [Drawing.Font]::new('Times New Roman',22,[Drawing.FontStyle]::Regular,[Drawing.GraphicsUnit]::Pixel)
$format = [Drawing.StringFormat]::new()
$format.Alignment = [Drawing.StringAlignment]::Center
$stroke = [Drawing.Pen]::new($leader,1.6)
$digital = [Drawing.Pen]::new($leader,2.6)
$digital.DashStyle = [Drawing.Drawing2D.DashStyle]::Dot
$digital.DashCap = [Drawing.Drawing2D.DashCap]::Round

function Paint-OriginalRegion([int]$x,[int]$y,[int]$width,[int]$height) {
    $rect = [Drawing.Rectangle]::new($x,$y,$width,$height)
    $graphics.DrawImage($previous,$rect,$rect,[Drawing.GraphicsUnit]::Pixel)
}

function Fade-Background([int]$x,[int]$y,[int]$width,[int]$height,$direction) {
    $rect = [Drawing.Rectangle]::new($x,$y,$width,$height)
    $fade = [Drawing.Drawing2D.LinearGradientBrush]::new(
        $rect,[Drawing.Color]::FromArgb(0,$background),$background,$direction)
    try { $graphics.FillRectangle($fade,$rect) }
    finally { $fade.Dispose() }
}

function Write-Label($value,[single]$x,[single]$y,$color=$ink,$font=$labelFont) {
    $brush = [Drawing.SolidBrush]::new($color)
    try { $graphics.DrawString($value,$font,$brush,[Drawing.PointF]::new($x,$y),$format) }
    finally { $brush.Dispose() }
}

try {
    $graphics.Clear($background)
    $graphics.DrawImageUnscaledAndClipped($previous,[Drawing.Rectangle]::new(0,0,654,446))
    Paint-OriginalRegion 0 446 260 80
    Fade-Background 0 510 260 16 ([Drawing.Drawing2D.LinearGradientMode]::Vertical)
    Fade-Background 260 430 394 16 ([Drawing.Drawing2D.LinearGradientMode]::Vertical)
    # Soft seam on blank paper only. The left-hand graphics remain at 1:1 scale.
    Fade-Background 633 0 21 446 ([Drawing.Drawing2D.LinearGradientMode]::Horizontal)
    Fade-Background 235 446 25 80 ([Drawing.Drawing2D.LinearGradientMode]::Horizontal)
    $paper = [Drawing.SolidBrush]::new($background)
    try { $graphics.FillRectangle($paper,612,340,43,11) }
    finally { $paper.Dispose() }

    $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $bounds = [Drawing.Rectangle]::new(795,50,1410,802)
    $placement = [Drawing.Rectangle]::new(744,63,1072,610)

    # Dashed electronic connection runs to the phase encoder controller.
    $graphics.DrawLines($digital,[Drawing.PointF[]]@(
        [Drawing.PointF]::new(612,345), [Drawing.PointF]::new(672,345),
        [Drawing.PointF]::new(672,425), [Drawing.PointF]::new(1170,425),
        [Drawing.PointF]::new(1170,353)))
    $graphics.DrawImage($render,$placement,$bounds,[Drawing.GraphicsUnit]::Pixel)

    Write-Label '532 nm laser' 873 98
    $graphics.DrawLine($stroke,873,132,873,151)
    Write-Label 'Reflective encoder' 1082 164
    $graphics.DrawLine($stroke,1085,197,1092,252)
    Write-Label 'LCOS 1' 1295 25
    Write-Label 'LCOS 2' 1373 444
    $graphics.DrawLine($stroke,1373,440,1373,420)
    Write-Label 'LCOS 3' 1711 188
    $graphics.DrawLine($stroke,1711,221,1711,232)
    Write-Label 'QWP + PBS' 1546 417
    $graphics.DrawLines($stroke,[Drawing.PointF[]]@(
        [Drawing.PointF]::new(1627,435),[Drawing.PointF]::new(1647,435),[Drawing.PointF]::new(1663,453)))

    $graphics.DrawLine($stroke,1808,527,1858,527)
    Write-Label 'LCP output' 1952 505 $blue
    Write-Label '96 × 96' 1952 542 $ink $measureFont
    $graphics.DrawLine($stroke,1489,553,1523,553)
    Write-Label 'RCP output' 1398 530 $orange
    Write-Label '96 × 96' 1398 566 $ink $measureFont

    $canvas.Save((Join-Path $out 'Fig1_dual_polarization_blender.png'),[Drawing.Imaging.ImageFormat]::Png)
} finally {
    $digital.Dispose()
    $stroke.Dispose()
    $format.Dispose()
    $labelFont.Dispose()
    $measureFont.Dispose()
    $graphics.Dispose()
    $canvas.Dispose()
    $render.Dispose()
    $previous.Dispose()
}
