import click


def test_prompts(runner):
    @click.command()
    def test():
        if click.confirm("Foo"):
            click.echo("yes!")
        else:
            click.echo("no :(")

    result = runner.invoke(test, input="y\n")
    assert not result.exception
    assert result.output == "Foo [y/N]: y\nyes!\n"

    result = runner.invoke(test, input="\n")
    assert not result.exception
    assert result.output == "Foo [y/N]: \nno :(\n"

    result = runner.invoke(test, input="n\n")
    assert not result.exception
    assert result.output == "Foo [y/N]: n\nno :(\n"

    @click.command()
    def test_no():
        if click.confirm("Foo", default=True):
            click.echo("yes!")
        else:
            click.echo("no :(")

    result = runner.invoke(test_no, input="y\n")
    assert not result.exception
    assert result.output == "Foo [Y/n]: y\nyes!\n"

    result = runner.invoke(test_no, input="\n")
    assert not result.exception
    assert result.output == "Foo [Y/n]: \nyes!\n"

    result = runner.invoke(test_no, input="n\n")
    assert not result.exception
    assert result.output == "Foo [Y/n]: n\nno :(\n"


def test_confirm_repeat(runner):
    cli = click.Command(
        "cli", params=[click.Option(["--a/--no-a"], default=None, prompt=True)]
    )
    result = runner.invoke(cli, input="\ny\n")
    assert result.output == "A [y/n]: \nError: invalid input\nA [y/n]: y\n"


def test_confirm_display_suffix(runner):
    @click.command()
    def test():
        click.confirm("Foo", display=click.ConfirmDisplay(prompt_suffix="? "))

    result = runner.invoke(test, input="y\n")
    assert not result.exception
    assert result.output == "Foo [y/N]? y\n"


def test_confirm_display_hide_default(runner):
    @click.command()
    def test():
        click.confirm("Foo", display=click.ConfirmDisplay(show_default=False))

    result = runner.invoke(test, input="y\n")
    assert not result.exception
    assert result.output == "Foo: y\n"


def test_confirm_display_defaults():
    display = click.ConfirmDisplay()
    assert display.prompt_suffix == ": "
    assert display.show_default is True
