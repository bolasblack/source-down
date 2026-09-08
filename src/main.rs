// {% spec "cli-001" %}
// {% spec "cli-005" %}
use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(
    name = "source-down",
    version,
    about = "Weave authored Markdown, source comments, and code into traceable pages"
)]
#[command(
    after_help = format!("{}\nMarkdown: .md narrative inputs. Built-in: include (id, lines).\nExit codes: 0 success, 1 generation error, 2 usage/configuration error, 130 cancelled.", source_down::lang::help())
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Render each source file into its own Markdown page
    Render {
        #[arg(required = true, num_args = 1..)]
        paths: Vec<PathBuf>,
        /// Project root; all other relative paths use this directory
        #[arg(long, default_value = ".")]
        root: PathBuf,
        /// TOML configuration (default: source-down.toml when present)
        #[arg(long)]
        config: Option<PathBuf>,
        /// Output root containing pages/ and reports/ (default: .source-down)
        #[arg(long)]
        output_dir: Option<PathBuf>,
    },
}

fn main() {
    let cli = Cli::parse();
    let cancelled = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    if let Err(error) = source_down::platform::register_cancellation(cancelled.clone()) {
        eprintln!("source-down: cannot register cancellation handler: {error}");
        std::process::exit(1);
    }
    let result = match cli.command {
        Commands::Render {
            root,
            config,
            paths,
            output_dir,
        } => source_down::engine::run(
            &root,
            config.as_deref(),
            &paths,
            output_dir.as_deref(),
            cancelled,
        ),
    };
    if let Err(error) = result {
        eprintln!("source-down: {error}");
        std::process::exit(error.exit_code);
    }
}
