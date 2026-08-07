These test submission exercise the check for TeX Produced
Postscript and PDF files.

Most test files either demonstrate TeX Produced PS/PDF or
normal non-TeX-Produced files.

PDF test files:

0611002.pdf
0706.3810.pdf			- Not TeX produced
0706.3906.pdf
0706.3927.pdf
0706.3971.pdf 			- Not TeX produced
0706.4328.pdf
0706.4412.pdf
2738685LaTeX.pdf
2745765withCairoFonts.pdf    	- New: looks for Cairo fonts
2748220withCairoCreator.pdf  	- New: looks for Cairo software
GalluzziBalkancom2018.pdf
astro-ph-0610480.ethanneil.20289.pdf
astro-ph-0703077.jf_sauvage.10062.pdf
astro-ph.arimoto.4168.pdf
astro-ph.ewhelan.18488.pdf
math0607661.tudateru.25992.tsuda_takenawa.pdf
notex_compositionality.pdf	- Not TeX produced
sparsemult6.pdf

Postscript test files:

0190238.ps
astro-ph.fdarcang.22633.ps
hep-th-0701130.pmho.24929.ps
math.kristaly.24457.ps
math.suri.13734.ps
notex_kkpants.eps		- Not TeX produced
notex_orddps5.eps		- Not TeX produced
physics-0611280.pdomokos.2059.eps
simple_tex_produced.ps



The legacy tests contains a small number of test files that
produced false negative and false positive results.

These files indicate the 'failure' of this check to clearly
distinguish a TeX-produced or non-TeX-produced file.

0609584.pdf		- TeX produced but not detected as such
paperfinal.PDF		- Not TeX produced but detected as TeX produced
submit_0169105.ps	- TeX produced but not detected as such

