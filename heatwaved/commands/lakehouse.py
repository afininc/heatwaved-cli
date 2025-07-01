
import oci
import typer
from oci.exceptions import ServiceError
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from heatwaved.config.manager import ConfigManager

app = typer.Typer()
console = Console()


@app.command("setup")
def setup_lakehouse(
    compartment_id: str = typer.Option(
        None, help="Compartment OCID (will list available if not provided)"
    ),
    dynamic_group_name: str = typer.Option("HeatWaveBucket-dG", help="Name for the dynamic group"),
    policy_name: str = typer.Option("HeatWaveBucket-Policy", help="Name for the policy"),
    show_only: bool = typer.Option(
        False, "--show-only", help="Only show what would be created without executing"
    ),
):
    """Set up Dynamic Group and Policy for HeatWave Lakehouse to access Object Storage."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1)

    # Check OCI configuration
    oci_config = config_manager.load_oci_config()
    if not oci_config or not oci_config.get('configured'):
        console.print(
            "[red]Error: OCI configuration not found. "
            "Please run 'heatwaved init --oci' first.[/red]"
        )
        raise typer.Exit(1)

    try:
        # Load OCI config
        config_path = oci_config['config_path']
        profile_name = oci_config.get('profile', 'DEFAULT')

        config = oci.config.from_file(
            file_location=config_path,
            profile_name=profile_name
        )

        identity_client = oci.identity.IdentityClient(config)

        # Get tenancy OCID
        tenancy_id = config["tenancy"]

        # If compartment not specified, let user select
        if not compartment_id:
            compartment_id = _select_compartment(identity_client, tenancy_id)
            if not compartment_id:
                console.print("[red]No compartment selected.[/red]")
                raise typer.Exit(1) from None

        # Get compartment details
        try:
            compartment = identity_client.get_compartment(compartment_id).data
            compartment_name = compartment.name
        except ServiceError:
            console.print(f"[red]Error: Invalid compartment ID: {compartment_id}[/red]")
            raise typer.Exit(1) from None

        console.print("\n[bold]HeatWave Lakehouse Setup[/bold]")
        console.print(f"[dim]Compartment: {compartment_name} ({compartment_id})[/dim]")
        console.print(f"[dim]Dynamic Group: {dynamic_group_name}[/dim]")
        console.print(f"[dim]Policy: {policy_name}[/dim]")

        # Check if we have an identity domain
        identity_domain = _get_identity_domain(identity_client, tenancy_id)

        # Create matching rule for dynamic group
        matching_rule = (
            f"ALL{{resource.type='mysqldbsystem', "
            f"resource.compartment.id = '{compartment_id}'}}"
        )

        # Create policy statements
        policy_statements = [
            f"Allow dynamic-group {dynamic_group_name} to read buckets "
            f"in compartment id {compartment_id}",
            f"Allow dynamic-group {dynamic_group_name} to read objects "
            f"in compartment id {compartment_id}",
        ]

        # If identity domain exists, update policy statements
        if identity_domain:
            policy_statements = [
                f"Allow dynamic-group '{identity_domain}'/{dynamic_group_name} "
                f"to read buckets in compartment id {compartment_id}",
                f"Allow dynamic-group '{identity_domain}'/{dynamic_group_name} "
                f"to read objects in compartment id {compartment_id}",
            ]

        # Show what will be created
        console.print("\n[bold]Dynamic Group Configuration:[/bold]")
        console.print(f"Name: {dynamic_group_name}")
        console.print(
            f"Description: Dynamic group for HeatWave Lakehouse to access "
            f"Object Storage in {compartment_name}"
        )
        console.print(f"Matching Rule: [cyan]{matching_rule}[/cyan]")

        console.print("\n[bold]Policy Configuration:[/bold]")
        console.print(f"Name: {policy_name}")
        console.print("Description: Policy for HeatWave Lakehouse to access Object Storage")
        console.print("Statements:")
        for stmt in policy_statements:
            console.print(f"  [cyan]{stmt}[/cyan]")

        if show_only:
            console.print("\n[yellow]--show-only flag set. Resources not created.[/yellow]")
            return

        # Confirm creation
        if not Confirm.ask("\nDo you want to create these resources?", default=True):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        # Create dynamic group
        try:
            console.print("\n[bold]Creating Dynamic Group...[/bold]")

            create_dynamic_group_details = oci.identity.models.CreateDynamicGroupDetails(
                compartment_id=tenancy_id,  # Dynamic groups are always in tenancy root
                name=dynamic_group_name,
                matching_rule=matching_rule,
                description=(
                    f"Dynamic group for HeatWave Lakehouse to access "
                    f"Object Storage in {compartment_name}"
                ),
            )

            dynamic_group = identity_client.create_dynamic_group(
                create_dynamic_group_details
            ).data

            console.print(f"[green]✓ Dynamic group created: {dynamic_group.id}[/green]")

        except ServiceError as e:
            if "already exists" in str(e):
                console.print(
                    f"[yellow]⚠ Dynamic group '{dynamic_group_name}' already exists[/yellow]"
                )
                # Try to get existing dynamic group
                dynamic_groups = identity_client.list_dynamic_groups(
                    compartment_id=tenancy_id,
                    name=dynamic_group_name
                ).data
                if dynamic_groups:
                    dynamic_group = dynamic_groups[0]
                    console.print(f"[dim]Using existing dynamic group: {dynamic_group.id}[/dim]")
            else:
                console.print(f"[red]✗ Failed to create dynamic group: {e.message}[/red]")
                raise typer.Exit(1) from None

        # Create policy
        try:
            console.print("\n[bold]Creating Policy...[/bold]")

            create_policy_details = oci.identity.models.CreatePolicyDetails(
                compartment_id=compartment_id,  # Policy in the target compartment
                name=policy_name,
                statements=policy_statements,
                description="Policy for HeatWave Lakehouse to access Object Storage",
            )

            policy = identity_client.create_policy(
                create_policy_details
            ).data

            console.print(f"[green]✓ Policy created: {policy.id}[/green]")

        except ServiceError as e:
            if "already exists" in str(e):
                console.print(f"[yellow]⚠ Policy '{policy_name}' already exists[/yellow]")
            else:
                console.print(f"[red]✗ Failed to create policy: {e.message}[/red]")
                raise typer.Exit(1) from None

        console.print("\n[green]✓ HeatWave Lakehouse setup completed![/green]")
        console.print(
            "\n[dim]Your MySQL DB Systems in this compartment can now access "
            "Object Storage buckets.[/dim]"
        )

    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {str(e)}[/red]")
        raise typer.Exit(1) from None


@app.command("list-buckets")
def list_buckets(
    compartment_id: str = typer.Option(
        None, help="Compartment OCID (will list available if not provided)"
    ),
):
    """List Object Storage buckets accessible to HeatWave Lakehouse."""
    config_manager = ConfigManager()

    if not config_manager.is_initialized():
        console.print(
            "[red]Error: HeatWave configuration not found. "
            "Please run 'heatwaved init' first.[/red]"
        )
        raise typer.Exit(1)

    # Check OCI configuration
    oci_config = config_manager.load_oci_config()
    if not oci_config or not oci_config.get('configured'):
        console.print(
            "[red]Error: OCI configuration not found. "
            "Please run 'heatwaved init --oci' first.[/red]"
        )
        raise typer.Exit(1)

    try:
        # Load OCI config
        config_path = oci_config['config_path']
        profile_name = oci_config.get('profile', 'DEFAULT')

        config = oci.config.from_file(
            file_location=config_path,
            profile_name=profile_name
        )

        identity_client = oci.identity.IdentityClient(config)
        object_storage_client = oci.object_storage.ObjectStorageClient(config)

        # Get namespace
        namespace = object_storage_client.get_namespace().data

        # Get tenancy OCID
        tenancy_id = config["tenancy"]

        # If compartment not specified, let user select
        if not compartment_id:
            compartment_id = _select_compartment(identity_client, tenancy_id)
            if not compartment_id:
                console.print("[red]No compartment selected.[/red]")
                raise typer.Exit(1) from None

        # List buckets
        console.print(f"\n[bold]Listing buckets in compartment {compartment_id}[/bold]")

        buckets = object_storage_client.list_buckets(
            namespace_name=namespace,
            compartment_id=compartment_id
        ).data

        if not buckets:
            console.print("[yellow]No buckets found in this compartment.[/yellow]")
            return

        # Create table
        table = Table(title="Object Storage Buckets", show_header=True)
        table.add_column("Bucket Name", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Storage Tier", style="yellow")

        for bucket in buckets:
            table.add_row(
                bucket.name,
                bucket.time_created.strftime("%Y-%m-%d %H:%M"),
                bucket.storage_tier or "Standard",
            )

        console.print(table)
        console.print(f"\n[dim]Total buckets: {len(buckets)}[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Error listing buckets: {str(e)}[/red]")
        raise typer.Exit(1) from None


def _select_compartment(identity_client, tenancy_id: str) -> str:
    """Let user select a compartment from available compartments."""
    console.print("\n[bold]Available Compartments:[/bold]")

    try:
        # Get all compartments
        compartments = []

        # Add root compartment (tenancy)
        tenancy = identity_client.get_tenancy(tenancy_id).data
        compartments.append({
            'id': tenancy_id,
            'name': f"{tenancy.name} (root)",
            'description': tenancy.description,
        })

        # Get child compartments
        child_compartments = identity_client.list_compartments(
            compartment_id=tenancy_id,
            compartment_id_in_subtree=True,
            access_level="ACCESSIBLE"
        ).data

        for comp in child_compartments:
            if comp.lifecycle_state == "ACTIVE":
                compartments.append({
                    'id': comp.id,
                    'name': comp.name,
                    'description': comp.description,
                })

        # Display compartments
        for i, comp in enumerate(compartments, 1):
            console.print(f"{i}. [cyan]{comp['name']}[/cyan]")
            if comp['description']:
                console.print(f"   [dim]{comp['description']}[/dim]")
            console.print(f"   [dim]ID: {comp['id']}[/dim]")
            console.print()

        # Get user selection
        while True:
            choice = Prompt.ask(
                "Select compartment number",
                default="1",
            )
            try:
                index = int(choice) - 1
                if 0 <= index < len(compartments):
                    return compartments[index]['id']
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a number.[/red]")

    except Exception as e:
        console.print(f"[red]Error listing compartments: {str(e)}[/red]")
        return None


def _get_identity_domain(identity_client, tenancy_id: str) -> str:
    """Get the identity domain name if using identity domains."""
    try:
        # Try to list domains - this will fail if not using identity domains
        domains = identity_client.list_domains(
            compartment_id=tenancy_id
        ).data

        if domains:
            # Return the first active domain
            for domain in domains:
                if domain.lifecycle_state == "ACTIVE":
                    return domain.display_name

    except Exception:
        # If listing domains fails, we're not using identity domains
        pass

    return None
