from PIL import Image, ImageOps, ImageFilter, ImageFont, ImageDraw
import aggdraw

Img_Size = (480, 320)

def add_corners(im, radius):
    # Rounds the corners of a PIL image
    im = im.convert("RGBA")
    mask = Image.new('L', im.size, 0)
    draw = aggdraw.Draw(mask)
    brush = aggdraw.Brush("white")
    w, h = im.size
    draw.rectangle((0, radius, w, h - radius), brush)
    draw.rectangle((radius, 0, w - radius, h), brush)
    draw.ellipse((0, 0, radius * 2, radius * 2), brush)
    draw.ellipse((w - radius * 2, 0, w, radius * 2), brush)
    draw.ellipse((0, h - radius * 2, radius * 2, h), brush)
    draw.ellipse((w - radius * 2, h - radius * 2, w, h), brush)

    draw.flush()
    im.putalpha(mask)
    return im

def transform_background(im):
    background = ImageOps.fit(im, (480, 320), Image.Resampling.LANCZOS)
    blured_background = background.filter(ImageFilter.GaussianBlur(15))
    # blured_background.show()
    return blured_background

def transform_thumbnail(im):
    thumbnail = im.resize((160, 160), Image.Resampling.LANCZOS)
    thumbnail_rounded = add_corners(thumbnail, 10)
    # thumbnail_rounded.show()
    return thumbnail_rounded

def truncate_text(text, max_length):
    if len(text) <= max_length:
        return text
    else:
        return text[:max_length - 3] + "..."
    
def interpolate(f_co, t_co, interval):
    det_co =[(t - f) / interval for f , t in zip(f_co, t_co)]
    for i in range(interval):
        yield [round(f + det * i) for f, det in zip(f_co, det_co)]

    
def imageposition(draw, text, font, im):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    image_width, _ = im.size
    x = (image_width - text_width) / 2
    return x

def main_image(title, artist, thumbnail, background):
    im = background.convert("RGBA")

    scrim = Image.new("RGBA", im.size, 0)
    draw_scrim = ImageDraw.Draw(scrim)

    t_co = (0, 0, 0, 204) # Black with 80% opacity
    f_co = (0, 0, 0, 0)   # Black with 0% opacity

    for y, color in enumerate(interpolate(f_co, t_co, im.height)):
        draw_scrim.line([(0, y), (im.width, y)], tuple(color), width=1)

    im = Image.alpha_composite(im, scrim)

    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("Delius-Regular.ttf", size=14)
    except IOError:
        print("Font file not found, using default font.")
        font = ImageFont.load_default() # Fallback
    
    title = truncate_text(title, 40)
    artist = truncate_text(artist, 22)
    
    draw.text((imageposition(draw, title, font, im), 216), title, fill=(255,255,255), font=font, align="center")
    draw.text((imageposition(draw, artist, font, im), 231), artist, fill=(255,255,255), font=font, align="center")


    im.paste(thumbnail, (160, 45), thumbnail)

    return im

if __name__ == '__main__':
    im = Image.open("ab67616d0000b27334f194f0e52087042c2a70a5.jpeg")
    background = transform_background(im)
    thumbnail = transform_thumbnail(im)
    im_txt = main_image("Brother Louie Mix '98 (feat. Eric Singleton) - Radio Edit", "Modern Talking", thumbnail, background)
    im_txt.show()