import io

from PIL import Image

from src.creator_image_service import resize_for_delivery


def test_resize_caps_long_edge_and_keeps_orientation():
    image = Image.new("RGB", (3200, 800), "red")
    source = io.BytesIO()
    image.save(source, format="PNG")

    _, width, height = resize_for_delivery(source.getvalue(), max_edge=1600)

    assert (width, height) == (1600, 400)


def test_resize_converts_transparent_png_to_jpeg():
    image = Image.new("RGBA", (32, 16), (255, 0, 0, 128))
    source = io.BytesIO()
    image.save(source, format="PNG")

    resized, width, height = resize_for_delivery(source.getvalue())

    with Image.open(io.BytesIO(resized)) as result:
        assert result.format == "JPEG"
        assert result.mode == "RGB"
        assert (width, height) == (32, 16)
