
import typer

from heatwaved.commands import config, init, test

app = typer.Typer(
    name="heatwaved",
    help="A CLI tool for Oracle MySQL HeatWave POC demonstrations",
    no_args_is_help=True,
)

app.add_typer(init.app, name="init", help="Initialize HeatWave configuration")
app.add_typer(test.app, name="test", help="Test HeatWave and OCI connections")
app.add_typer(config.app, name="config", help="Manage HeatWave configuration")

if __name__ == "__main__":
    app()
