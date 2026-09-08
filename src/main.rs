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
    after_help = format!("{}\nMarkdown: .md narrative inputs. Built-in: include (id, lines), link (path).\nExit codes: 0 success, 1 generation error, 2 usage/configuration error, 130 cancelled.", source_down::lang::help())
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(clap::Args)]
struct GenerationArgs {
    #[arg(required = true, num_args = 1..)]
    paths: Vec<PathBuf>,
    /// Project root; all other relative paths use this directory
    #[arg(long, default_value = ".")]
    root: PathBuf,
    /// TOML configuration (default: source-down.toml when present)
    #[arg(long)]
    config: Option<PathBuf>,
    /// Output root containing pages/, reports/ and search/ (default: .source-down)
    #[arg(long)]
    output_dir: Option<PathBuf>,
}

#[derive(Subcommand)]
enum Commands {
    /// Read a snapshot handle, or a current file's entity/section with --id
    Read {
        target: String,
        /// Select a current file's entity/section by name or JSON structural path
        #[arg(long, conflicts_with_all=["snapshot","cursor","context","occurrence","config","output_dir"])]
        id: Option<String>,
        /// UTF-8 byte offset returned by the previous read
        #[arg(long)]
        offset: Option<usize>,
        /// Adjacent fragments on each side (0..5, default: 0)
        #[arg(long)]
        context: Option<usize>,
        /// Choose an occurrence before expanding repeated content
        #[arg(long)]
        occurrence: Option<String>,
        /// Continue a sources, occurrences or input_files list
        #[arg(long, conflicts_with_all=["offset","context","occurrence"])]
        cursor: Option<String>,
        #[arg(long)]
        json: bool,
        #[arg(long)]
        snapshot: bool,
        #[arg(long, default_value = ".")]
        root: PathBuf,
        #[arg(long)]
        config: Option<PathBuf>,
        #[arg(long)]
        output_dir: Option<PathBuf>,
    },
    /// Find fragments in the last complete generation snapshot
    Search {
        query: String,
        #[arg(long)]
        path: Option<String>,
        #[arg(long, default_value="10", value_parser=clap::value_parser!(u32).range(1..=100))]
        limit: u32,
        #[arg(long)]
        json: bool,
        /// Read stored content without checking current project files
        #[arg(long)]
        snapshot: bool,
        #[arg(long, default_value = ".")]
        root: PathBuf,
        #[arg(long)]
        config: Option<PathBuf>,
        #[arg(long)]
        output_dir: Option<PathBuf>,
    },
    /// Render each source file into its own Markdown page
    Render(GenerationArgs),
    /// Regenerate complete pages as project files change
    Watch {
        #[command(flatten)]
        generation: GenerationArgs,
        /// Use content polling for filesystems that do not deliver native notifications
        #[arg(long)]
        poll: bool,
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
        Commands::Read {
            target,
            id,
            offset,
            context,
            occurrence,
            cursor,
            json,
            snapshot,
            root,
            config,
            output_dir,
        } => {
            if let Some(id) = id {
                source_down::search::read_file(&root, &target, &id, offset, &cancelled).and_then(
                    |result| {
                        source_down::search::print_file_result(
                            &result, json, &root, &target, &id, &cancelled,
                        )
                    },
                )
            } else {
                let options = source_down::search::ReadOptions {
                    offset,
                    context,
                    occurrence,
                    cursor,
                };
                options
                    .validate()
                    .and_then(|()| {
                        source_down::search::Reader::open(
                            &root,
                            config.as_deref(),
                            output_dir.as_deref(),
                            snapshot,
                            cancelled.clone(),
                        )
                    })
                    .and_then(|reader| reader.read(&target, &options))
                    .and_then(|result| source_down::search::print_result(&result, json, &cancelled))
            }
        }
        Commands::Search {
            query,
            path,
            limit,
            json,
            snapshot,
            root,
            config,
            output_dir,
        } => source_down::search::validate_query(&query, path.as_deref(), limit as usize)
            .and_then(|()| {
                source_down::search::Reader::open(
                    &root,
                    config.as_deref(),
                    output_dir.as_deref(),
                    snapshot,
                    cancelled.clone(),
                )
            })
            .and_then(|reader| reader.query(&query, path.as_deref(), limit as usize))
            .and_then(|result| source_down::search::print_result(&result, json, &cancelled)),
        Commands::Render(args) => source_down::engine::run(
            &args.root,
            args.config.as_deref(),
            &args.paths,
            args.output_dir.as_deref(),
            cancelled,
        ),
        Commands::Watch {
            generation: args,
            poll,
        } => source_down::watch::run(
            &args.root,
            args.config.as_deref(),
            &args.paths,
            args.output_dir.as_deref(),
            poll,
            cancelled,
        ),
    };
    if let Err(error) = result {
        eprintln!("source-down: {error}");
        std::process::exit(error.exit_code);
    }
}
