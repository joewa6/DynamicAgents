using Random

struct ParamSpec
    name::String
    lo::Float64
    hi::Float64
end

function parameter_specs()
    specs = ParamSpec[
        ParamSpec("food_rate", 0.2, 12.0),
        ParamSpec("mutation", 0.0, 0.65),
        ParamSpec("target_pop", 40.0, 150.0),
    ]

    for k in 1:N_GENES
        push!(specs, ParamSpec("mean_$(GENE_NAMES[k])", Float64(GENE_LO[k]), Float64(GENE_HI[k])))
        push!(specs, ParamSpec("std_$(GENE_NAMES[k])", 0.03 * Float64(GENE_HI[k] - GENE_LO[k]),
                               0.35 * Float64(GENE_HI[k] - GENE_LO[k])))
    end
    return specs
end

function latin_hypercube(n::Int, specs::Vector{ParamSpec}; seed::Int=1)
    rng = MersenneTwister(seed)
    samples = [Dict{String,Float64}() for _ in 1:n]

    for spec in specs
        order = randperm(rng, n)
        for i in 1:n
            u = (order[i] - rand(rng)) / n
            samples[i][spec.name] = spec.lo + u * (spec.hi - spec.lo)
        end
    end

    return samples
end
