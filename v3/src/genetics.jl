const INIT_GENE_FORMS = ["uniform" for _ in 1:N_GENES]
const INIT_GENE_MEAN = Float32[(GENE_LO[k] + GENE_HI[k]) * 0.5f0 for k in 1:N_GENES]
const INIT_GENE_STD = Float32[(GENE_HI[k] - GENE_LO[k]) * 0.25f0 for k in 1:N_GENES]

function _standard_sample(form::AbstractString)::Float32
    if form == "normal"
        return randn(Float32)
    elseif form == "bimodal"
        side = rand(Bool) ? 1.0f0 : -1.0f0
        return (side + randn(Float32) * 0.30f0) / 1.044f0
    elseif form == "low-skew"
        return (rand(Float32)^2 - 1f0 / 3f0) / 0.2982f0
    elseif form == "high-skew"
        return ((1f0 - rand(Float32)^2) - 2f0 / 3f0) / 0.2982f0
    else
        return (rand(Float32) - 0.5f0) * 3.4641016f0
    end
end

function rand_gene(k::Int, form::AbstractString, mean::Float32, std::Float32)::Float32
    return clamp(mean + std * _standard_sample(form), GENE_LO[k], GENE_HI[k])
end

function rand_genes(forms=INIT_GENE_FORMS,
                    means::AbstractVector{Float32}=INIT_GENE_MEAN,
                    stds::AbstractVector{Float32}=INIT_GENE_STD)::Vector{Float32}
    g = Vector{Float32}(undef, N_GENES)
    @inbounds for k in 1:N_GENES
        g[k] = rand_gene(k, forms[k], means[k], stds[k])
    end
    return g
end

function mutate!(g::Vector{Float32}, rate::Float32)
    @inbounds for k in 1:N_GENES
        rand() > 0.7f0 && continue
        span = GENE_HI[k] - GENE_LO[k]
        g[k] += randn(Float32) * rate * span * 0.15f0
        g[k] = clamp(g[k], GENE_LO[k], GENE_HI[k])
    end
end

function crossover(g1::AbstractVector{Float32}, g2::AbstractVector{Float32},
                   rate::Float32)::Vector{Float32}
    child = Vector{Float32}(undef, N_GENES)
    @inbounds for k in 1:N_GENES
        alpha = rand(Float32)
        child[k] = alpha * g1[k] + (1f0 - alpha) * g2[k]
    end
    mutate!(child, rate)
    return child
end

# Normalised Euclidean distance in gene space, used for selectivity and kin checks.
function gene_dist(g1::AbstractVector{Float32}, g2::AbstractVector{Float32})::Float32
    d = 0.0f0
    @inbounds for k in 1:N_GENES
        span = GENE_HI[k] - GENE_LO[k]
        delta = (g1[k] - g2[k]) / span
        d += delta * delta
    end
    return sqrt(d / N_GENES)
end
