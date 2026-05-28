FROM julia:1.12

WORKDIR /app

COPY Project.toml Manifest.toml ./
RUN julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

COPY . .

ENV JULIA_NUM_THREADS=auto
EXPOSE 8000

CMD ["julia", "--project=.", "run.jl"]
