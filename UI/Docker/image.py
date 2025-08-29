from PIL import Image, ImageOps, ImageFilter, ImageFont, ImageDraw, ImageColor
import aggdraw

Img_Size = (480, 320)

global txt_widht
txt_widht = []

def largest(arr):
    # Returns the largest element in the array
    try:
        ans = max(arr)
        return ans
    except ValueError:
        print("Error: The array is empty.")
        return 0

def add_corners(im, radius):
    # Rounds the corners of a PIL image
    try:
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
    except Exception as e:
        print(f"Error in add_corners: {e}")
        return im

def get_dominant_color(image):
    # Returns the dominant color of the image as an RGB tuple
    try:
        image = image.convert('RGB')
        quantized_img = image.quantize(colors=8, method=Image.Quantize.FASTOCTREE)
        colors = quantized_img.getcolors(quantized_img.size[0] * quantized_img.size[1])
        if not colors:
            print("Could not retrieve colors from the image.")
            return None
        dominant_color_info = max(colors, key=lambda item: item[0])
        count, color_index = dominant_color_info
        palette = quantized_img.getpalette()
        dominant_rgb = tuple(palette[color_index * 3 : color_index * 3 + 3])
        return dominant_rgb
    except Exception as e:
        print(f"Error in get_dominant_color: {e}")
        return (128, 128, 128)  # Return a default color

def transform_background(im):
    # Transforms the image to a blurred background of fixed size
    try:
        background = ImageOps.fit(im, (480, 320), Image.Resampling.LANCZOS)
        blured_background = background.filter(ImageFilter.GaussianBlur(15))
        return blured_background
    except Exception as e:
        print(f"Error in transform_background: {e}")
        return im

def thumbnail_blur(thumbnail):
    # Creates a blurred rectangle using the dominant color of the thumbnail
    try:
        im = Image.new("RGBA", (400, 400), (0,0,0,0))
        draw = ImageDraw.Draw(im)
        draw.rectangle([100, 100, 300, 300], fill=get_dominant_color(thumbnail)) # type: ignore
        blured = im.filter(ImageFilter.GaussianBlur(40))
        return blured
    except Exception as e:
        print(f"Error in thumbnail_blur: {e}")
        return thumbnail

def transform_thumbnail(im):
    # Resizes and rounds the corners of the image for thumbnail use
    try:
        thumbnail = im.resize((160, 160), Image.Resampling.LANCZOS)
        thumbnail_rounded = add_corners(thumbnail, 10)
        return thumbnail_rounded
    except Exception as e:
        print(f"Error in transform_thumbnail: {e}")
        return im

def truncate_text(text, max_length):
    # Truncates text to a maximum length, adding "..." if needed
    if len(text) <= max_length:
        return text
    else:
        return text[:max_length - 3] + "..."

def interpolate(f_co, t_co, interval):
    # Generates color interpolation between two RGBA tuples
    det_co =[(t - f) / interval for f , t in zip(f_co, t_co)]
    for i in range(interval):
        yield [round(f + det * i) for f, det in zip(f_co, det_co)]

def imageposition(draw, text, font, im):
    # Calculates the x position to center the text on the image
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        txt_widht.append(text_width)
        image_width, _ = im.size
        x = (image_width - text_width) / 2
        return x
    except Exception as e:
        print(f"Error in imageposition: {e}")
        return 0

def main_image(title, artist, thumbnail, background):
    # Composes the main image with background, thumbnail, and text overlays
    try:
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
            font = ImageFont.truetype("/home/niclas/Coding/desk/UI/Docker/Delius-Regular.ttf", size=14)
        except IOError:
            print("Font file not found, using default font.")
            font = ImageFont.load_default() # Fallback
        title = truncate_text(title, 40)
        artist = truncate_text(artist, 22)
        im_pos_title = imageposition(draw, title, font, im)
        im_pos_artist = imageposition(draw, artist, font, im)
        thumbnailblur = thumbnail_blur(thumbnail)
        im.paste(thumbnailblur, (40, -75), thumbnailblur)
        rect_overlay_size = []
        for x in im.size:
            x = x * 4
            rect_overlay_size.append(x)
        rect_overlay = Image.new("RGBA", rect_overlay_size, (0, 0, 0, 0)) # type: ignore
        draw_rect = ImageDraw.Draw(rect_overlay)
        max_txt_widht = largest(txt_widht)
        rect_x = ((im.size[0] / 2) - (max_txt_widht / 2)) * 4 - 25
        rect_start = (rect_x, 215*4)
        rect_end = (rect_x + max_txt_widht*4 + 50, 252*4)
        draw_rect.rounded_rectangle([rect_start, rect_end], radius=16, fill=(0, 0, 0, 170)) # type: ignore
        rect_overlay_blured = rect_overlay.filter(ImageFilter.GaussianBlur(10))
        rect_overlay_scaled = ImageOps.scale(rect_overlay_blured, 0.25, resample=Image.Resampling.LANCZOS)
        im = Image.alpha_composite(im, rect_overlay_scaled)
        draw = ImageDraw.Draw(im)
        draw.text((im_pos_title, 216), title, fill=(255,255,255), font=font, align="center")
        draw.text((im_pos_artist, 231), artist, fill=(255,255,255), font=font, align="center")
        im.paste(thumbnail, (160, 45), thumbnail)
        return im
    except Exception as e:
        print(f"Error in main_image: {e}")
        return background

if __name__ == '__main__':
    # Entry point for testing the image generation

    try:
        im = Image.open("ab67616d0000b27334f194f0e52087042c2a70a5.jpeg")
        background = transform_background(im)
        thumbnail = transform_thumbnail(im)
        im_txt = main_image("Brother Louie Mix '98 (feat. Eric Singleton) - Radio Edit", "Modern Talking", thumbnail, background)
        im_txt.show()
    except Exception as e:
        print(f"Error in __main__: {e}")