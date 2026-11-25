$ErrorActionPreference = 'Stop'
$outDir = 'D:\srdd\models\figure'
$spec = Get-Content -LiteralPath (Join-Path $outDir 'labels.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$scale = 36.0
$ppApp = New-Object -ComObject PowerPoint.Application
$ppApp.DisplayAlerts = 1
$deck = $null
try {
    $deck = $ppApp.Presentations.Add(0)
    $deck.PageSetup.SlideWidth = [single]($spec.width * $scale)
    $deck.PageSetup.SlideHeight = [single]($spec.height * $scale)
    $slide = $deck.Slides.Add(1, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.ForeColor.RGB = 16777215
    $bg = $slide.Shapes.AddPicture((Join-Path $outDir 'research_base.png'),0,-1,0,0,[single]($spec.width*$scale),[single]($spec.height*$scale))
    $bg.Name = 'Blender geometry - editable in the accompanying blend'
    foreach ($label in $spec.labels) {
        $width = [double]$label.width * $scale * 1.10 + 6
        $height = [double]$label.height * $scale + 3
        $x = [double]$label.x * $scale
        if ($label.align -eq 'CENTER') { $x -= $width / 2 }
        $top = ([double]$spec.height - [double]$label.baseline - [double]$label.size * 1.04) * $scale
        $box = $slide.Shapes.AddTextbox(1,[single]$x,[single]$top,[single]$width,[single]$height)
        $box.Name = 'Editable label - ' + $label.text
        $tf = $box.TextFrame
        $tf.MarginLeft=0; $tf.MarginRight=0; $tf.MarginTop=0; $tf.MarginBottom=0
        $tf.WordWrap=0
        $tr=$tf.TextRange
        $tr.Text=$label.text
        $tr.Font.Name='Arial'
        $tr.Font.Size=[single]([double]$label.size*$scale)
        $tr.Font.Bold= $(if ($label.bold) {-1} else {0})
        $hex=$spec.colors.($label.color).TrimStart('#')
        $red=[Convert]::ToInt32($hex.Substring(0,2),16)
        $green=[Convert]::ToInt32($hex.Substring(2,2),16)
        $blue=[Convert]::ToInt32($hex.Substring(4,2),16)
        $tr.Font.Color.RGB=$red+256*$green+65536*$blue
        $tr.ParagraphFormat.SpaceBefore=0; $tr.ParagraphFormat.SpaceAfter=0
        if ($label.align -eq 'CENTER') { $tr.ParagraphFormat.Alignment=2 } else { $tr.ParagraphFormat.Alignment=1 }
    }
    $notes=@'
Research concept, not experimental performance data. Two 96x96 intensity targets are electronically encoded into one 24x24 phase map. Three effective Jones stages produce two circular-polarization outputs. Output illustrations are target appearances, not trained reconstructions. A 4x sampling increase per axis does not itself prove diffraction-limit super-resolution.

References and visual conventions:
Isil et al., Super-resolution image display using diffractive decoders, arXiv:2206.07281. https://arxiv.org/abs/2206.07281
Li et al., Polarization multiplexed diffractive computing, Light: Science & Applications (2022). https://doi.org/10.1038/s41377-022-00849-x
Liu et al., Polarization-multiplexed diffractive neural networks for multi-task classification based on liquid crystals, Optics Letters 50, 5446-5449 (2025). https://doi.org/10.1364/OL.571548
Local derivation: 偏振调制演化推导.pdf. Reference code: 双通道偏振调制.txt.
The published works have different hardware and tasks; their results are not attributed to this proposed system.

All labels are native editable PowerPoint text. Geometry and illustrative patterns are Blender-rendered assets; the source Blender file includes the source apparatus scene and the composition scene. Reference picture supplied by the user informed the white background, section divisions and colour-coded annotation style.
'@
    $slide.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text=$notes
    $deck.SaveAs((Join-Path $outDir 'research_v005.pptx'),24)
    $slide.Export((Join-Path $outDir 'ppt_preview.png'),'PNG',3000,1875)
    Write-Output ('PPT_SAVED: ' + $deck.Slides.Count + ' slide; ' + $slide.Shapes.Count + ' shapes')
} finally {
    if ($deck) {$deck.Close()}
    $ppApp.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($ppApp)
}
