from app.analyzers.content import ContentAnalyzer

analyzer = ContentAnalyzer()


def test_high_buzzword_density():
    html = """<html><body><p>
    We leverage cutting-edge, innovative solutions to empower your business and streamline
    your workflow. Our seamless, robust platform elevates your brand in today's digital landscape.
    Unlock your potential and drive results with our world-class, best-in-class end-to-end
    comprehensive solutions. Revolutionize your approach with transformative, holistic strategies.
    We synergize and empower teams to leverage scalable, dynamic, game-changing innovations.
    </p></body></html>"""
    result = analyzer.analyze(html)
    assert result.score > 50
    assert len(result.evidence) > 3


def test_plain_text_scores_low():
    html = """<html><body><p>
    This website is about my garden. I grow tomatoes, peppers, and herbs.
    In the spring I plant seeds and in the fall I harvest vegetables.
    The soil needs regular watering and sunshine to produce a good crop.
    My neighbors often ask me for tips on growing their own food at home.
    Gardening is a relaxing hobby that connects you to the natural world.
    </p></body></html>"""
    result = analyzer.analyze(html)
    assert result.score < 20


def test_too_short_abstains():
    html = "<html><body><p>Hello world</p></body></html>"
    result = analyzer.analyze(html)
    assert result.score == 0
    assert "Not enough text" in result.evidence[0]


def test_weight():
    assert analyzer.weight == 0.30
