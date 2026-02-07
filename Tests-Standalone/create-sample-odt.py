"""
Create a sample ODT file with URLs for testing.
"""

from odf.opendocument import OpenDocumentText
from odf.text import P
from odf.style import Style, TextProperties, ParagraphProperties
from odf import style


def create_sample_odt(output_path: str) -> None:
    """
    Create a sample ODT file with various URLs.

    Args:
        output_path: Path where the ODT file will be saved
    """
    # Create a new ODT document
    doc = OpenDocumentText()

    # Add a title style
    title_style = Style(name='Title', family='paragraph')
    title_style.addElement(ParagraphProperties(textalign='center'))
    title_props = TextProperties(fontsize='18pt', fontweight='bold')
    title_style.addElement(title_props)
    doc.styles.addElement(title_style)

    # Add a bold style
    bold_style = Style(name='Bold', family='text')
    bold_style.addElement(TextProperties(fontweight='bold'))
    doc.automaticstyles.addElement(bold_style)

    # Add title
    title = P(stylename=title_style, text='Sample ODT Document with URLs')
    doc.text.addElement(title)

    # Add content paragraphs
    paragraphs = [
        '',
        'This is a test ODT document containing various URLs.',
        '',
        'YouTube Videos:',
        'https://www.youtube.com/watch?v=jNQXAC9IVRw',
        'https://youtu.be/dQw4w9WgXcQ',
        '',
        'Greek Music Channel:',
        'https://www.youtube.com/@GreekMusicChannel/videos',
        '',
        'Documentation and Resources:',
        '- Python documentation: https://docs.python.org/3/',
        '- yt-dlp GitHub: https://github.com/yt-dlp/yt-dlp',
        '- ODF Toolkit: https://odfpy.readthedocs.io/en/latest/',
        '',
        'Multiple URLs in one paragraph: Check out https://www.example.com and also visit https://test.example.org for more info.',
        '',
        'Some URLs with paths:',
        'https://en.wikipedia.org/wiki/OpenDocument',
        'http://www.w3.org/TR/NOTE-datetime',
        '',
        'End of document.',
    ]

    for text in paragraphs:
        p = P(text=text)
        doc.text.addElement(p)

    # Save the document
    doc.save(output_path)
    print(f'Created sample ODT file: {output_path}')


if __name__ == '__main__':
    create_sample_odt(output_path='Tests/sample-urls.odt')
