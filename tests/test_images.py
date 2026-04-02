from app.analyzers.images import ImageAnalyzer

analyzer = ImageAnalyzer()


def test_unsplash_images_detected():
    html = '''<html><body>
    <img src="https://images.unsplash.com/photo-1234567890123-abc.jpg" alt="hero"/>
    <img src="https://images.unsplash.com/photo-9876543210987-xyz.jpg" alt="team"/>
    </body></html>'''
    result = analyzer.analyze(html)
    assert result.score > 50
    assert any("unsplash" in e for e in result.evidence)


def test_framer_cdn_detected():
    html = '<html><body><img src="https://framerusercontent.com/image-abc123.jpg"/></body></html>'
    result = analyzer.analyze(html)
    assert result.score > 0


def test_local_images_score_zero():
    html = '<html><body><img src="/images/photo.jpg"/><img src="/assets/team.png"/></body></html>'
    result = analyzer.analyze(html)
    assert result.score == 0


def test_no_images_score_zero():
    html = "<html><body><p>No images here</p></body></html>"
    result = analyzer.analyze(html)
    assert result.score == 0


def test_weight():
    assert analyzer.weight == 0.10
