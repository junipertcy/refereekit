import subprocess, pathlib

HERE = pathlib.Path(__file__).parent
TEX = HERE / "sample_paper.tex"
PDF = HERE / "sample_paper.pdf"

def build() -> pathlib.Path:
    if PDF.exists() and PDF.stat().st_mtime >= TEX.stat().st_mtime:
        return PDF
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(HERE), str(TEX)],
        check=True, capture_output=True,
    )
    return PDF

if __name__ == "__main__":
    print(build())
