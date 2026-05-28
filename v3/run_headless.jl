# julia run_headless.jl --rounds 50000 --food 8 --mutation 0.15 --out results/run1.csv
include("src/config.jl")
include("src/genetics.jl")
include("src/bonds.jl")
include("src/simulation.jl")

using Statistics

function parse_cli_args(args)
    opts = Dict{String,String}()
    i = 1
    while i <= length(args)
        arg = args[i]
        if startswith(arg, "--")
            key = arg[3:end]
            i == length(args) && error("Missing value for --$key")
            opts[key] = args[i + 1]
            i += 2
        else
            error("Unexpected argument: $arg")
        end
    end
    return opts
end

format_cell(x) = x isa AbstractFloat ? string(round(x, digits=4)) : string(x)

function run_headless(; rounds=50_000, food_rate=3, target_pop=TARGET_POP,
                        mutation=0.15f0, out="results/run.csv", save_every=50)
    s = Simulation()
    out_dir = dirname(out)
    !isempty(out_dir) && mkpath(out_dir)

    header = ["round", "pop", "n_bonds", "avg_energy", GENE_NAMES...]
    rows = Vector{Any}[]

    for r in 1:rounds
        tick!(s; food_rate, mutation, target_pop)

        if r % save_every == 0
            idx = findall(s.alive)
            n = length(idx)
            row = Any[r, n, length(s.bonds.data),
                      n > 0 ? mean(s.e[idx]) : 0.0]
            for k in 1:N_GENES
                push!(row, n > 0 ? mean(s.genes[idx, k]) : 0.0)
            end
            push!(rows, row)
            r % 5000 == 0 && @info "round $r  pop=$n  bonds=$(length(s.bonds.data))"
        end
    end

    open(out, "w") do f
        println(f, join(header, ","))
        for row in rows
            println(f, join(format_cell.(row), ","))
        end
    end
    @info "Saved $(length(rows)) records -> $out"
end

opts = parse_cli_args(ARGS)
run_headless(
    rounds=parse(Int, get(opts, "rounds", "50000")),
    food_rate=parse(Float32, get(opts, "food", "3")),
    target_pop=parse(Int, get(opts, "target-pop", string(TARGET_POP))),
    mutation=parse(Float32, get(opts, "mutation", "0.15")),
    out=get(opts, "out", "results/run.csv"),
    save_every=parse(Int, get(opts, "save-every", "50")),
)
