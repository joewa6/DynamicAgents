using LinearAlgebra, Statistics

function csv_escape(x)
    s = string(x)
    occursin(Regex("[,\"\n]"), s) || return s
    return "\"" * replace(s, "\"" => "\"\"") * "\""
end

function write_csv(path::String, rows::Vector{Dict{String,Float64}}, columns::Vector{String})
    dir = dirname(path)
    !isempty(dir) && mkpath(dir)
    open(path, "w") do io
        println(io, join(columns, ","))
        for row in rows
            println(io, join([csv_escape(round(get(row, col, NaN), digits=6)) for col in columns], ","))
        end
    end
end

function add_pca!(rows::Vector{Dict{String,Float64}}, param_cols::Vector{String})
    isempty(rows) && return
    n = length(rows)
    if n < 2
        for row in rows
            row["pca1"] = 0.0
            row["pca2"] = 0.0
        end
        return
    end
    p = length(param_cols)
    x = zeros(Float64, n, p)
    for i in 1:n, j in 1:p
        x[i, j] = rows[i][param_cols[j]]
    end

    mu = vec(mean(x, dims=1))
    sigma = vec(std(x, dims=1))
    sigma .= ifelse.((sigma .== 0) .| .!isfinite.(sigma), 1.0, sigma)
    z = (x .- mu') ./ sigma'
    covar = (z' * z) / max(n - 1, 1)
    eig = eigen(Symmetric(covar))
    order = sortperm(eig.values, rev=true)
    vectors = eig.vectors[:, order[1:min(2, length(order))]]
    proj = z * vectors

    for i in 1:n
        rows[i]["pca1"] = proj[i, 1]
        rows[i]["pca2"] = size(proj, 2) >= 2 ? proj[i, 2] : 0.0
    end
end

function js_rows(rows::Vector{Dict{String,Float64}}, columns::Vector{String})
    parts = String[]
    for row in rows
        fields = ["\"$col\":$(get(row, col, NaN))" for col in columns]
        push!(parts, "{" * join(fields, ",") * "}")
    end
    return "[" * join(parts, ",") * "]"
end

function write_html_report(path::String, rows::Vector{Dict{String,Float64}},
                           param_cols::Vector{String}, metric_cols::Vector{String})
    dir = dirname(path)
    !isempty(dir) && mkpath(dir)
    columns = vcat(param_cols, metric_cols, ["pca1", "pca2", "structure_score"])
    data = js_rows(rows, columns)
    params_js = "[" * join(["\"$p\"" for p in param_cols], ",") * "]"
    metrics_js = "[" * join(["\"$m\"" for m in metric_cols], ",") * "]"

    html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DynamicAgents V4 Scan</title>
<style>
body{margin:0;background:#090910;color:#c9d2e3;font:12px Menlo,Consolas,monospace}
header{padding:12px 16px;border-bottom:1px solid #202034;display:flex;gap:18px;align-items:center}
h1{font-size:16px;margin:0;color:#d8e0f0}
#grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px}
.panel{border:1px solid #202034;background:#0e0e19;padding:10px;min-height:310px}
.panel h2{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#68738c;margin:0 0 8px}
canvas{width:100%;height:280px;display:block;background:#080811}
select{background:#151528;color:#c9d2e3;border:1px solid #2c2c48;padding:4px;font:inherit}
.controls{display:flex;gap:8px;margin-bottom:8px}
</style>
</head>
<body>
<header><h1>DynamicAgents V4 Scan</h1><span id="summary"></span></header>
<div id="grid">
  <section class="panel"><h2>PCA: all sampled parameters</h2><canvas id="pca"></canvas></section>
  <section class="panel"><h2>Custom scatter</h2><div class="controls"><select id="xsel"></select><select id="ysel"></select></div><canvas id="custom"></canvas></section>
  <section class="panel"><h2>Environment vs structure score</h2><canvas id="env"></canvas></section>
  <section class="panel"><h2>Top gene priors vs structure score</h2><canvas id="genes"></canvas></section>
</div>
<script>
const rows = $data;
const params = $params_js;
const metrics = $metrics_js;
document.getElementById('summary').textContent = rows.length + ' runs';
const scoreColor = s => {
  const vals = rows.map(r => r.structure_score).sort((a,b)=>a-b);
  const lo = vals[0], hi = vals[vals.length-1], t = (s-lo)/(hi-lo || 1);
  return 'hsl(' + (240*t) + ',70%,58%)';
};
function bounds(data, key){
  const vals = data.map(r=>r[key]).filter(Number.isFinite);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if(lo === hi){ lo -= 1; hi += 1; }
  return [lo, hi];
}
function plot(canvas, data, xKey, yKey, colorBy='structure_score'){
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  const dpr = devicePixelRatio || 1;
  canvas.width = rect.width*dpr; canvas.height = rect.height*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);
  const pad = 34, w = rect.width-pad-10, h = rect.height-pad-12;
  const [xmin,xmax] = bounds(data,xKey), [ymin,ymax] = bounds(data,yKey);
  ctx.strokeStyle='#25253a'; ctx.lineWidth=1; ctx.strokeRect(pad,10,w,h);
  ctx.fillStyle='#68738c'; ctx.fillText(xKey,pad,rect.height-8); ctx.save(); ctx.translate(10,10+h); ctx.rotate(-Math.PI/2); ctx.fillText(yKey,0,0); ctx.restore();
  for(const r of data){
    const x = pad + ((r[xKey]-xmin)/(xmax-xmin))*w;
    const y = 10 + h - ((r[yKey]-ymin)/(ymax-ymin))*h;
    ctx.fillStyle = scoreColor(r[colorBy]);
    ctx.beginPath(); ctx.arc(x,y,3,0,Math.PI*2); ctx.fill();
  }
}
function fillSelect(sel, options, chosen){
  sel.innerHTML = options.map(o =>
    '<option value="' + o + '" ' + (o===chosen ? 'selected' : '') + '>' + o + '</option>'
  ).join('');
}
const allCols = params.concat(metrics).concat(['structure_score','pca1','pca2']);
fillSelect(xsel, allCols, 'food_rate'); fillSelect(ysel, allCols, 'structure_score');
xsel.onchange = ysel.onchange = () => plot(custom, rows, xsel.value, ysel.value);
function drawAll(){
  plot(pca, rows, 'pca1', 'pca2');
  plot(custom, rows, xsel.value, ysel.value);
  plot(env, rows, 'food_rate', 'structure_score');
  plot(genes, rows, 'mean_coop', 'structure_score');
}
addEventListener('resize', drawAll); drawAll();
</script>
</body>
</html>
"""
    open(path, "w") do io
        write(io, html)
    end
end
