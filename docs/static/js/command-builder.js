(function() {
  const PRESETS = ["FOAF", "SCHEMA", "DCTERMS", "GOODRELATIONS", "NFO",
                   "ORG", "CINELAB", "EPPLAN", "URBANIOT", "SYNTH-1", "SYNTH-2", "SYNTH-3"];
  const TASKS = ["taxonomy", "domain", "range", "property"];
  const MAKI_MODELS = ["qwen3.5-122b", "llama-3.3-70b", "qwen3.6-36b", "ministral-3-14b"];
  const OPENAI_MODELS = ["gpt-5.6-luna", "gpt-5.6-luna+web", "gpt-5.6-luna+web3"];
  const ALL_MODELS = MAKI_MODELS.concat(OPENAI_MODELS);
  const FORMATS = ["plain", "prefix", "full"];
  const MINK_TASKS = ["taxonomy", "domain", "range"];
  const $ = id => document.getElementById(id);

  function Dropdown(mount, placeholder, items, onchange, multi = false) {
    const root = document.createElement("div"); root.className = "dd";
    root.innerHTML = `
      <button type="button" class="dd-btn">
        <span class="dd-label">${placeholder}</span>
        <svg class="caret" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4.427 6.427A.6.6 0 0 1 4.851 5.4h6.298a.6.6 0 0 1 .424 1.027L8.424 9.576a.6.6 0 0 1-.848 0Z"/>
        </svg>
      </button>
      <div class="dd-menu"></div>`;
    mount.replaceChildren(root);
    const menu = root.querySelector(".dd-menu");
    const label = root.querySelector(".dd-label");
    let current = items;
    let selected = new Set();
    const dd = {
      get value() { return multi ? [...selected] : (selected.values().next().value || ""); },
      get list() { return [...selected]; },
    };

    function render() {
      menu.innerHTML = "";
      for (const it of current) {
        const [value, note] = Array.isArray(it) ? it : [it, ""];
        const el = document.createElement("div");
        el.className = "dd-item" + (selected.has(value) ? " selected" : "");
        el.innerHTML = `<svg class="tick" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.75.75 0 1 1 1.06-1.06l2.72 2.72 6.72-6.72a.75.75 0 0 1 1.06 0Z"/></svg>
          <span>${value}</span>${note ? `<span class="note">${note}</span>` : ""}`;
        el.addEventListener("click", e => {
          if (multi) e.stopPropagation();
          if (multi && selected.has(value)) selected.delete(value);
          else { if (!multi) selected.clear(); selected.add(value); }
          if (!multi) root.classList.remove("open");
          render(); refresh(); onchange();
        });
        menu.append(el);
      }
    }
    function refresh() {
      const vals = [...selected];
      label.textContent = !vals.length ? placeholder
        : (multi && vals.length > 2 ? `${vals.length} selected` : vals.join(", "));
      root.classList.toggle("has-value", vals.length > 0);
    }
    root.querySelector(".dd-btn").addEventListener("click", e => {
      e.stopPropagation();
      document.querySelectorAll(".dd.open").forEach(o => o !== root && o.classList.remove("open"));
      root.classList.toggle("open");
    });
    render();
    return dd;
  }
  document.addEventListener("click", () =>
    document.querySelectorAll(".dd.open").forEach(o => o.classList.remove("open")));
  document.addEventListener("keydown", e => { if (e.key === "Escape")
    document.querySelectorAll(".dd.open").forEach(o => o.classList.remove("open")); });

  const ddCommand = Dropdown($("ddCommand"), "choose a command", [
    ["run", "one command per combination"],
    ["grid", "one call per method and ontology"],
    ["aggregate", "rebuild tables, no API calls"],
    ["generate-synthetic", "one time synthetic ontology (GET)"],
  ], () => build());
  const ddMethod = Dropdown($("ddMethod"), "Methods",
    ["ts-guessing", "guided-prompting", "min-k"], () => build(), true);
  const ddPreset = Dropdown($("ddPreset"), "Ontologies", PRESETS, () => build(), true);
  const ddTask = Dropdown($("ddTask"), "Tasks", TASKS, () => build(), true);
  const ddModel = Dropdown($("ddModel"), "Models", ALL_MODELS, () => build(), true);
  const ddFormat = Dropdown($("ddFormat"), "Formats", FORMATS, () => build(), true);

  const tasksFor = m => m === "min-k" ? MINK_TASKS : TASKS;
  const modelsFor = m => m === "min-k" ? MAKI_MODELS : ALL_MODELS;

  function build() {
    const cmd = ddCommand.value;
    const methods = ddMethod.list, presets = ddPreset.list;
    const tasks = ddTask.list, models = ddModel.list, formats = ddFormat.list;

    const synthetic = cmd === "generate-synthetic";
    $("extrasRuns").hidden = synthetic;
    $("extrasSynthetic").hidden = !synthetic;
    if (synthetic) {
      for (const id of ["stepMethod", "stepPreset", "stepAxes"]) $(id).classList.add("disabled");
      $("stepExtras").classList.remove("disabled");
      $("axesHint").textContent = "";
      const line = "uv run generate_synthetic.py" + ($("dryRun").checked ? " --dry-run" : "");
      $("output").textContent = line;
      $("copyBtn").disabled = false;
      return;
    }

    $("stepMethod").classList.toggle("disabled", !cmd);
    $("stepPreset").classList.toggle("disabled", !(cmd && methods.length && cmd !== "aggregate"));
    $("stepAxes").classList.toggle("disabled", !(cmd && cmd !== "aggregate" && methods.length && presets.length));
    $("stepExtras").classList.toggle("disabled", !(cmd && methods.length && (cmd === "aggregate" || presets.length)));

    const hints = [];
    if (cmd === "run") hints.push("multiple selections produce one command per combination");
    if (cmd === "grid") hints.push("empty selection = flag omitted, the CLI then uses its defaults");
    if (cmd === "grid" && models.some(m => OPENAI_MODELS.includes(m)) && models.some(m => MAKI_MODELS.includes(m)))
      hints.push("mixed model families are split into separate grid calls");
    if (methods.includes("min-k")) hints.push("min-k lines automatically skip property and OpenAI models");
    $("axesHint").textContent = hints.join(" · ");

    $("limit").disabled = cmd === "aggregate";
    const limit = cmd === "aggregate" ? "" : $("limit").value;
    const dir = $("resultsDir").value.trim();
    let extras = "";
    if (limit) extras += " --limit " + limit;
    if (dir) extras += " --results-dir " + dir;

    const lines = [];
    if (cmd === "aggregate") {
      for (const method of methods)
        lines.push(`uv run main.py aggregate --method ${method}` + (dir ? " --results-dir " + dir : ""));
    } else if (cmd === "run" && methods.length && presets.length && tasks.length && models.length && formats.length) {
      for (const method of methods) {
        const mt = tasks.filter(t => tasksFor(method).includes(t));
        const mm = models.filter(m => modelsFor(method).includes(m));
        for (const preset of presets) for (const t of mt) for (const m of mm) for (const f of formats)
          lines.push(`uv run main.py run --method ${method} --ontology-preset ${preset} --task ${t} --model ${m} --format ${f}${extras}`);
      }
    } else if (cmd === "grid" && methods.length && presets.length) {
      for (const method of methods) {
        const mt = tasks.filter(t => tasksFor(method).includes(t));
        if (tasks.length && !mt.length) continue;
        const mm = models.filter(m => modelsFor(method).includes(m));
        if (models.length && !mm.length) continue;
        const families = models.length
          ? [mm.filter(m => MAKI_MODELS.includes(m)), mm.filter(m => OPENAI_MODELS.includes(m))].filter(g => g.length)
          : [[]];
        for (const preset of presets) for (const group of families) {
          let line = `uv run main.py grid --method ${method} --ontology-preset ${preset}`;
          if (mt.length) line += " --tasks " + mt.join(" ");
          if (group.length) line += " --models " + group.join(" ");
          if (formats.length) line += " --formats " + formats.join(" ");
          lines.push(line + extras);
        }
      }
    }

    const ready = lines.length > 0;
    $("output").textContent = ready ? lines.join("\n") : "uv run main.py ...";
    $("copyBtn").disabled = !ready;
  }

  for (const id of ["limit", "resultsDir"]) $(id).addEventListener("input", build);
  $("dryRun").addEventListener("change", build);

  $("copyBtn").addEventListener("click", async () => {
    const text = $("output").textContent;
    try { await navigator.clipboard.writeText(text); }
    catch { const ta = document.createElement("textarea"); ta.value = text;
            document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
    const btn = $("copyBtn");
    btn.textContent = "Copied!"; btn.classList.add("copied");
    setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1500);
  });

  build();
})();
