
import typer

from heatwaved.commands import init

app = typer.Typer(
    name="heatwaved",
    help="A CLI tool for Oracle MySQL HeatWave POC demonstrations",
    no_args_is_help=True,
)

app.add_typer(init.app, name="init", help="Initialize HeatWave configuration")

if __name__ == "__main__":
    app()
