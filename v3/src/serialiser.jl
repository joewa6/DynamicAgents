using JSON3

function serialise_frame(s::Simulation)::String
    idx = findall(s.alive)

    slot_to_fi = zeros(Int, MAX_POP)
    for (k, slot) in enumerate(idx)
        slot_to_fi[slot] = k
    end

    agents = (
        x=s.x[idx],
        y=s.y[idx],
        e=s.e[idx] ./ MAX_ENERGY,
        coop=s.genes[idx, G_COOP],
        open=s.genes[idx, G_OPENNESS],
        openness=s.genes[idx, G_OPENNESS],
        selectivity=s.genes[idx, G_SELECTIVITY],
        forgiveness=s.genes[idx, G_FORGIVENESS],
        kin_bias=s.genes[idx, G_KIN_BIAS],
        speed=(s.genes[idx, G_SPEED] .- GENE_LO[G_SPEED]) ./ (GENE_HI[G_SPEED] - GENE_LO[G_SPEED]),
        perception=(s.genes[idx, G_PERCEPTION] .- GENE_LO[G_PERCEPTION]) ./ (GENE_HI[G_PERCEPTION] - GENE_LO[G_PERCEPTION]),
        metabolism=(s.genes[idx, G_METABOLISM] .- GENE_LO[G_METABOLISM]) ./ (GENE_HI[G_METABOLISM] - GENE_LO[G_METABOLISM]),
        bond_thresh=(s.genes[idx, G_BOND_THRESH] .- GENE_LO[G_BOND_THRESH]) ./ (GENE_HI[G_BOND_THRESH] - GENE_LO[G_BOND_THRESH]),
        fertility=s.genes[idx, G_FERTILITY],
        uid=s.uid[idx],
        gen=s.gen[idx],
    )

    ab = active_bonds(s.bonds)
    bi = Int[]
    bj = Int[]
    bs = Float32[]
    for ((si, sj), bstate) in ab
        fi = slot_to_fi[si]
        fj = slot_to_fi[sj]
        (fi == 0 || fj == 0) && continue
        push!(bi, fi - 1)
        push!(bj, fj - 1)
        push!(bs, bstate.score)
    end

    rings_data = [(x=r.x, y=r.y, age=s.round - r.born) for r in s.rings]
    init_genes = (
        form=s.init_gene_form,
        mean=s.init_gene_mean,
        std=s.init_gene_std,
    )

    return JSON3.write((
        type="frame",
        round=s.round,
        agents=agents,
        bonds=(i=bi, j=bj, score=bs),
        rings=rings_data,
        food=(x=s.fx, y=s.fy),
        stats=sim_stats(s),
        init_genes=init_genes,
    ))
end
