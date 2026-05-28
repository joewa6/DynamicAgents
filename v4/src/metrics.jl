using Statistics

function gini(values::AbstractVector{<:Real})
    n = length(values)
    n == 0 && return 0.0
    sorted = sort(Float64.(values))
    total = sum(sorted)
    total <= 0 && return 0.0
    acc = 0.0
    for (i, v) in enumerate(sorted)
        acc += (2 * i - n - 1) * v
    end
    return acc / (n * total)
end

function find_root!(parent::Vector{Int}, x::Int)
    while parent[x] != x
        parent[x] = parent[parent[x]]
        x = parent[x]
    end
    return x
end

function union_root!(parent::Vector{Int}, a::Int, b::Int)
    ra = find_root!(parent, a)
    rb = find_root!(parent, b)
    ra != rb && (parent[rb] = ra)
end

function bond_graph_metrics(s::Simulation)
    alive_slots = findall(s.alive)
    n = length(alive_slots)
    n == 0 && return Dict{String,Float64}(
        "mean_bond_strength" => 0.0,
        "bond_density" => 0.0,
        "largest_component_size" => 0.0,
        "num_components" => 0.0,
        "modularity" => 0.0,
        "clustering_coefficient" => 0.0,
        "mean_degree" => 0.0,
        "degree_gini" => 0.0,
    )

    slot_to_node = Dict{Int,Int}()
    for (node, slot) in enumerate(alive_slots)
        slot_to_node[slot] = node
    end

    adj = falses(n, n)
    degree = zeros(Int, n)
    weights = Float64[]
    parent = collect(1:n)

    for ((si, sj), b) in active_bonds(s.bonds)
        haskey(slot_to_node, si) && haskey(slot_to_node, sj) || continue
        a = slot_to_node[si]
        c = slot_to_node[sj]
        adj[a, c] = true
        adj[c, a] = true
        degree[a] += 1
        degree[c] += 1
        push!(weights, Float64(b.score))
        union_root!(parent, a, c)
    end

    m = length(weights)
    possible = n * (n - 1) / 2
    density = possible > 0 ? m / possible : 0.0
    mean_strength = m > 0 ? mean(weights) : 0.0

    component_sizes = Dict{Int,Int}()
    for node in 1:n
        root = find_root!(parent, node)
        component_sizes[root] = get(component_sizes, root, 0) + 1
    end
    largest_component = maximum(values(component_sizes))
    num_components = length(component_sizes)

    clustering_vals = Float64[]
    for node in 1:n
        neigh = findall(adj[node, :])
        d = length(neigh)
        d < 2 && continue
        links = 0
        for a_idx in 1:(d - 1), b_idx in (a_idx + 1):d
            adj[neigh[a_idx], neigh[b_idx]] && (links += 1)
        end
        push!(clustering_vals, links / (d * (d - 1) / 2))
    end
    clustering = isempty(clustering_vals) ? 0.0 : mean(clustering_vals)

    modularity = 0.0
    if m > 0
        for root in keys(component_sizes)
            nodes = [node for node in 1:n if find_root!(parent, node) == root]
            internal = 0
            deg_sum = 0
            for node in nodes
                deg_sum += degree[node]
            end
            for a_idx in 1:(length(nodes) - 1), b_idx in (a_idx + 1):length(nodes)
                adj[nodes[a_idx], nodes[b_idx]] && (internal += 1)
            end
            modularity += internal / m - (deg_sum / (2 * m))^2
        end
    end

    return Dict{String,Float64}(
        "mean_bond_strength" => mean_strength,
        "bond_density" => density,
        "largest_component_size" => largest_component / n,
        "num_components" => Float64(num_components),
        "modularity" => modularity,
        "clustering_coefficient" => clustering,
        "mean_degree" => mean(degree),
        "degree_gini" => gini(degree),
    )
end

function gene_monoculture(s::Simulation)
    idx = findall(s.alive)
    isempty(idx) && return 1.0
    vals = Float64[]
    for k in 1:N_GENES
        span = Float64(GENE_HI[k] - GENE_LO[k])
        span <= 0 && continue
        push!(vals, std(Float64.(s.genes[idx, k])) / span)
    end
    diversity = isempty(vals) ? 0.0 : mean(vals)
    return clamp(1.0 - diversity / 0.20, 0.0, 1.0)
end

function structure_score(row::Dict{String,Float64})
    extinction_penalty = row["extinction_time"] > 0 ? 2.0 : 0.0
    explosion_penalty = max(0.0, row["final_population"] - 170.0) / 30.0
    collapse_penalty = max(0.0, 20.0 - row["final_population"]) / 20.0
    return row["modularity"] +
           row["clustering_coefficient"] +
           0.40 * row["bond_density"] +
           0.20 * min(row["num_components"], 8.0) / 8.0 -
           extinction_penalty -
           collapse_penalty -
           explosion_penalty -
           row["monoculture_penalty"]
end
