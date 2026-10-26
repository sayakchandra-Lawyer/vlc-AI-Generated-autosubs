import pytest

from vlc_autosubs import cli, helper, installer, models


@pytest.fixture(autouse=True)
def nothing_downloaded(monkeypatch):
    monkeypatch.setattr(models, "is_downloaded", lambda name: False)


def answers(*replies):
    """A stand-in for input() that gives these replies, then end-of-input."""
    replies = list(replies)

    def read(prompt):
        if not replies:
            raise EOFError
        return replies.pop(0)
    return read


def ask(*replies, **kwargs):
    shown = []
    choice = models.ask(read=answers(*replies), write=shown.append, **kwargs)
    return choice, "\n".join(shown)


def test_enter_takes_the_recommendation():
    assert ask("", gpu=False)[0] == "small"
    assert ask("", gpu=True)[0] == "large-v3"


@pytest.mark.parametrize("reply, model", [
    ("1", "small"), ("2", "medium"), ("3", "large-v3"),
    ("Better", "medium"), ("best", "large-v3"), ("large", "large-v3"), ("small", "small"),
])
def test_numbers_and_words_both_work(reply, model):
    assert ask(reply, gpu=False)[0] == model


def test_wrong_answers_are_asked_again():
    choice, shown = ask("7", "maybe", "2", gpu=False)
    assert choice == "medium"
    assert shown.count("Please type 1, 2 or 3.") == 2


def test_current_choice_is_the_default():
    choice, shown = ask("", current="medium", gpu=False)
    assert choice == "medium"
    assert "your current choice" in shown


def test_no_input_at_all_takes_the_default():
    assert ask(gpu=False)[0] == "small"


def test_menu_explains_sizes_and_recommendation():
    _, shown = ask("", gpu=False)
    assert "480 MB download, recommended for this computer" in shown
    assert "3 GB download" in shown


def test_menu_says_what_needs_no_download(monkeypatch):
    monkeypatch.setattr(models, "is_included", lambda name: name == "small")
    monkeypatch.setattr(models, "is_downloaded", lambda name: name in ("small", "medium"))
    _, shown = ask("", gpu=False)
    assert "(included in this download, recommended for this computer)" in shown
    assert "(already downloaded)" in shown


def test_auto_means_the_recommended_model():
    assert models.effective("auto", gpu=False) == "small"
    assert models.effective(None, gpu=True) == "large-v3"
    assert models.effective("medium", gpu=False) == "medium"


def test_doctor_reports_the_chosen_model():
    results = {name: (ok, detail) for name, ok, detail in helper.doctor(model="medium")}
    ok, detail = results["model"]
    assert ok and detail.startswith("medium: not downloaded yet") and "1.5 GB" in detail


# --- the install command -------------------------------------------------

@pytest.fixture
def at_a_terminal(monkeypatch, fake_home):
    monkeypatch.setattr(cli, "_interactive", lambda: True)
    monkeypatch.setattr(models, "has_nvidia_gpu", lambda: False)
    downloads = []
    monkeypatch.setattr(helper, "download_model",
                        lambda name: downloads.append(name) or f"/cache/{name}")
    return downloads


def test_install_asks_then_downloads_the_choice(at_a_terminal, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", answers("2"))
    cli.main(["install"])
    assert installer.read_conf()["model"] == "medium"
    assert at_a_terminal == ["medium"]
    out = capsys.readouterr().out
    # "Done" only after the download, then the tip for a slow choice
    assert out.index("done, saved to") < out.index("Done.") < out.index("Tip:")


def test_interrupted_download_still_finishes_the_install(at_a_terminal, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", answers(""))

    def interrupted(name):
        raise KeyboardInterrupt
    monkeypatch.setattr(helper, "download_model", interrupted)
    cli.main(["install"])
    assert installer.read_conf()["model"] == "small"
    out = capsys.readouterr().out
    assert "The download stopped. That's OK" in out and "Done." in out


def test_no_question_without_a_terminal(fake_home, monkeypatch):
    monkeypatch.setattr(cli, "_interactive", lambda: False)
    monkeypatch.setattr("builtins.input", answers())  # would return the default
    cli.main(["install"])
    assert "model" not in installer.read_conf()


def test_no_question_when_the_model_is_given(at_a_terminal, monkeypatch):
    monkeypatch.setattr("builtins.input", answers("3"))
    cli.main(["install", "--model", "small"])
    assert installer.read_conf()["model"] == "small"
    assert at_a_terminal == []
