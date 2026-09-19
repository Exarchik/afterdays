"""Build full-cell icons + readable translucent footer (offline Pillow only)."""
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]/'assets'
WIDTHS=(48,56,64,80,96,128)
HEIGHT=72

def build():
    sources=[(Image.open(ROOT/'atlas_192.png').convert('RGBA'),16,128),
             (Image.open(ROOT/'trophies_192.png').convert('RGBA'),4,12)]
    icons=[]
    for image,cols,count in sources:
        for i in range(count):
            pic=image.crop((i%cols*192,i//cols*192,(i%cols+1)*192,(i//cols+1)*192))
            box=pic.getchannel('A').getbbox()
            icons.append(pic.crop(box) if box else pic)
    for width in WIDTHS:
        sheet=Image.new('RGBA',(16*width,9*HEIGHT))
        shade=Image.new('RGBA',(width,HEIGHT))
        for y in range(HEIGHT):
            alpha=round(215*max(0,(y-37)/(HEIGHT-38)))
            if alpha:shade.paste((12,18,17,alpha),(0,y,width,y+1))
        for n,original in enumerate(icons):
            pic=original.copy();pic.thumbnail((width-2,HEIGHT-2),Image.Resampling.LANCZOS)
            tile=Image.new('RGBA',(width,HEIGHT));tile.alpha_composite(pic,((width-pic.width)//2,(HEIGHT-pic.height)//2))
            tile.alpha_composite(shade)
            sheet.alpha_composite(tile,(n%16*width,n//16*HEIGHT))
        path=ROOT/f'inventory_{width}.png';temporary=path.with_suffix('.tmp.png')
        sheet.save(temporary,optimize=True)
        with Image.open(temporary) as check:check.load()
        temporary.replace(path)
    print('Built six full-cell inventory sheets.')

if __name__=='__main__':build()
