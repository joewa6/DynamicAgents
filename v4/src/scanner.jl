using Statistics

function apply_params!(s::Simulation, params::Dict{String,Float64})
    for k in 1:N_GENES
        set_init_gene!(
            s,
            k,
            "normal",
            Float32(params["mean_$(GENE_NAMES[k])"]),
            Float32(params["std_$(GENE_NAMES[k])"]),
        )
    end
    reset!(s)
end

function run_one(run_id::Int, params::Dict{String,Float64}; ticks::Int=5000)
    s = Simulation()
    apply_params!(s, params)

    pops = Int[]
    extinction_time = 0

    for t in 1:ticks
        tick!(
            s,
            food_rate=Float32(params["food_rate"]),
            mutation=Float32(params["mutation"]),
            target_pop=round(Int, params["target_pop"]),
        )
        pop = count(s.alive)
        push!(pops, pop)
        if pop == 0 && extinction_time == 0
            extinction_time = t
            break
        end
    end

    row = Dict{String,Float64}()
    for (k, v) in params
        row[k] = v
    end

    row["run_id"] = run_id
    row["final_population"] = isempty(pops) ? 0.0 : Float64(pops[end])
    row["mean_population"] = isempty(pops) ? 0.0 : mean(pops)
    row["population_variance"] = length(pops) > 1 ? var(pops) : 0.0
    row["extinction_time"] = Float64(extinction_time)
    row["monoculture_penalty"] = gene_monoculture(s)

    merge!(row, bond_graph_metrics(s))
    row["structure_score"] = structure_score(row)
    return row
end

function parse_args(args)
    opts = Dict{String,String}()
    n = isempty(args) || startswith(args[1], "--") ? 100 : parse(Int, args[1])
    i = isempty(args) || startswith(args[1], "--") ? 1 : 2
    while i <= length(args)
        key = args[i]
        startswith(key, "--") || error("Unexpected argument: $key")
        i == length(args) && error("Missing value for $key")
        opts[key[3:end]] = args[i + 1]
        i += 2
    end
    return n, opts
end

function run_scan(n::Int; ticks::Int=5000, seed::Int=1, out::String="v4/results/scan.csv")
    specs = parameter_specs()
    param_cols = ["run_id"; [s.name for s in specs]]
    metric_cols = [
        "final_population",
        "mean_population",
        "population_variance",
        "extinction_time",
        "mean_bond_strength",
        "bond_density",
        "largest_component_size",
        "num_components",
        "modularity",
        "clustering_coefficient",
        "mean_degree",
        "degree_gini",
        "monoculture_penalty",
    ]

    samples = latin_hypercube(n, specs; seed)
    rows = Dict{String,Float64}[]

    for i in 1:n
        row = run_one(i, samples[i]; ticks)
        push!(rows, row)
        @info "run $i/$n" score=round(row["structure_score"], digits=4) pop=row["final_population"]
    end

    add_pca!(rows, param_cols[2:end])
    columns = vcat(param_cols, metric_cols, ["structure_score", "pca1", "pca2"])
    write_csv(out, rows, columns)

    html = replace(out, r"\.csv$" => ".html")
    write_html_report(html, rows, param_cols[2:end], metric_cols)
    @info "saved results" csv=out html=html
end

function run_scanner_from_cli(args)
    n, opts = parse_args(args)
    run_scan(
        n;
        ticks=parse(Int, get(opts, "ticks", "5000")),
        seed=parse(Int, get(opts, "seed", "1")),
        out=get(opts, "out", "v4/results/scan.csv"),
    )
end
