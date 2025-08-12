import utils


def test_movie_title_from_url():
    url = "https://in.bookmyshow.com/movies/delhi/oppenheimer/ET0001234"
    assert utils.movie_title_from_url(url) == "Oppenheimer"
    url2 = "https://in.bookmyshow.com/ET0005678"
    assert utils.movie_title_from_url(url2) == "ET0005678"
    assert utils.movie_title_from_url("bad") == "Movie"


def test_titled():
    msg = utils.titled(
        {"url": "https://in.bookmyshow.com/movies/delhi/oppenheimer/ET0001234"}, "Hi"
    )
    assert msg.startswith("🎬 Oppenheimer\n")
    msg2 = utils.titled("https://in.bookmyshow.com/ET0005678", "Hello")
    assert "ET0005678" in msg2
