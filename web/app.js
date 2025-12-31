const stateUrl = "/api/state";
const selectUrl = "/api/select";
const refreshUrl = "/api/refresh-models";
const authUrl = "/api/provider-auth";

const providerListEl = document.getElementById("providerList");
const modelListEl = document.getElementById("modelList");
const modelItemsEl = document.getElementById("modelItems");
const modelFilterInputEl = document.getElementById("modelFilterInput");
const refreshBtnInlineEl = document.getElementById("refreshBtnInline");
const refreshStatusInlineEl = document.getElementById("refreshStatusInline");
const selectedProviderEl = document.getElementById("selectedProvider");
const selectedUrlEl = document.getElementById("selectedUrl");
const tokenInEl = document.getElementById("tokenIn");
const headerOverrideEl = document.getElementById("headerOverride");
const requestOverrideEl = document.getElementById("requestOverride");
const queryParamsEl = document.getElementById("queryParams");
const tokenParamEl = document.getElementById("tokenParam");
const tokenHeaderEl = document.getElementById("tokenHeader");
const tokenHeaderFormatEl = document.getElementById("tokenHeaderFormat");
const applyAuthBtn = document.getElementById("applyAuth");
const presetClaudeCLIBtn = document.getElementById("presetClaudeCLI");
const presetDefaultBtn = document.getElementById("presetDefault");
const presetQueryBtn = document.getElementById("presetQuery");
const presetBearerBtn = document.getElementById("presetBearer");
const presetDirectBtn = document.getElementById("presetDirect");
const presetXApiBtn = document.getElementById("presetXApi");
const reloadBtn = document.getElementById("reloadBtn");
const resetBtn = document.getElementById("resetBtn");

let refreshStatusText = "";
let modelFilterValue = "";
let refreshBusy = false;

let previewProviderName = null;

async function fetchState() {
  const res = await fetch(stateUrl);
  return res.json();
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    const helper = document.createElement("textarea");
    helper.value = text;
    document.body.appendChild(helper);
    helper.select();
    document.execCommand("copy");
    document.body.removeChild(helper);
  }
}

function renderProviders(state) {
  providerListEl.innerHTML = "";
  const selected = state.selected_provider;
  state.providers.forEach((provider) => {
    const card = document.createElement("div");
    card.className = "provider-card";
    const isSelected = provider.name === selected;
    const isPreview = provider.name === (previewProviderName || selected);
    if (isSelected) {
      card.classList.add("active");
    }
    if (isPreview && !isSelected) {
      card.classList.add("preview");
    }

    const header = document.createElement("div");
    header.className = "provider-header";

    const name = document.createElement("div");
    name.className = "provider-name";
    name.textContent = provider.name || "Unnamed";

    const btn = document.createElement("button");
    btn.className = "select-btn";
    btn.textContent = isSelected ? "Selected" : "Select";
    btn.disabled = isSelected;
    if (isSelected) {
      btn.classList.add("selected");
    }
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      selectProvider(provider.name);
    });

    const actions = document.createElement("div");
    actions.className = "provider-actions";

    const copyTokenBtn = document.createElement("button");
    copyTokenBtn.className = "mini-btn";
    copyTokenBtn.textContent = "Token";
    copyTokenBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      copyText(provider.api_key || "");
    });

    const copyUrlBtn = document.createElement("button");
    copyUrlBtn.className = "mini-btn";
    copyUrlBtn.textContent = "URL";
    copyUrlBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      copyText(provider.api_base_url || "");
    });

    actions.appendChild(copyTokenBtn);
    actions.appendChild(copyUrlBtn);
    actions.appendChild(btn);

    header.appendChild(name);
    header.appendChild(actions);

    const url = document.createElement("div");
    url.className = "provider-url";
    url.textContent = provider.api_base_url || "";

    const comment = document.createElement("div");
    comment.className = "provider-comment";
    comment.textContent = provider.comment || provider.note || "";

    card.appendChild(header);
    card.appendChild(url);
    if (comment.textContent) {
      card.appendChild(comment);
    }
    card.addEventListener("click", () => {
      previewProviderName = provider.name;
      renderModels(state);
      renderProviders(state);
    });
    providerListEl.appendChild(card);
  });
}

function renderModels(state) {
  const targetName = previewProviderName || state.selected_provider;
  const preview = state.providers.find((p) => p.name === targetName);
  const selected = state.providers.find((p) => p.name === state.selected_provider);
  let models = preview && Array.isArray(preview.models) ? preview.models : [];
  const filterRaw = modelFilterValue.trim().toLowerCase();
  if (filterRaw) {
    const keys = filterRaw.split(",").map((k) => k.trim()).filter(Boolean);
    models = models.filter((m) => keys.some((k) => m.toLowerCase().includes(k)));
  }
  modelItemsEl.innerHTML = "";
  models.forEach((model) => {
    const row = document.createElement("div");
    row.className = "model-row";

    const pill = document.createElement("div");
    pill.className = "model-pill";
    pill.textContent = model;

    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      copyModel(model);
    });

    row.appendChild(pill);
    row.appendChild(copyBtn);
    modelItemsEl.appendChild(row);
  });
  selectedProviderEl.textContent = selected ? selected.name : "None";
  selectedUrlEl.textContent = selected ? selected.api_base_url || "" : "";
}

async function copyModel(model) {
  const text = `/model ${model}`;
  await copyText(text);
}

function renderHeaderOverrides(state) {
  const overrides = state.header_overrides || [];
  const currentValue = headerOverrideEl.value;

  // 清空所有选项
  headerOverrideEl.innerHTML = "";

  // 添加所有选项
  overrides.forEach((override) => {
    const option = document.createElement("option");
    option.value = override;
    option.textContent = override;
    headerOverrideEl.appendChild(option);
  });

  // 恢复之前的值
  if (currentValue && overrides.includes(currentValue)) {
    headerOverrideEl.value = currentValue;
  }
}

function renderRequestOverrides(state) {
  const overrides = state.request_overrides || [];
  const currentValue = requestOverrideEl.value;

  // 清空所有选项
  requestOverrideEl.innerHTML = "";

  // 添加所有选项
  overrides.forEach((override) => {
    const option = document.createElement("option");
    option.value = override;
    option.textContent = override;
    requestOverrideEl.appendChild(option);
  });

  // 恢复之前的值
  if (currentValue && overrides.includes(currentValue)) {
    requestOverrideEl.value = currentValue;
  }
}

function renderAuth(state) {
  const override = state.selected_override || {};
  const hasOverride = Object.keys(override).length > 0;
  tokenInEl.value = override.token_in !== undefined ? override.token_in : "";
  headerOverrideEl.value = override.header_override || "";
  requestOverrideEl.value = override.request_override || "";
  queryParamsEl.value = override.query_params || "";
  tokenParamEl.value = override.token_param || "";
  tokenHeaderEl.value = override.token_header || (hasOverride ? "" : "Authorization");
  tokenHeaderFormatEl.value = override.token_header_format || (hasOverride ? "" : "Bearer {token}");
}

async function selectProvider(name) {
  await fetch(selectUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider: name }),
  });
  previewProviderName = name;
  await refresh();
}

async function applyAuthOverride(payload) {
  const state = await fetchState();
  const provider = state.selected_provider;
  if (!provider) return;
  await fetch(authUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, override: payload }),
  });
  await refresh();
}

async function refreshModels() {
  refreshBusy = true;
  refreshStatusText = "Refreshing...";
  refreshBtnInlineEl.disabled = true;
  refreshBtnInlineEl.textContent = "Refreshing";
  refreshStatusInlineEl.textContent = refreshStatusText;
  const state = await fetchState();
  const current = previewProviderName || state.selected_provider;
  try {
    const res = await fetch(refreshUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: current }),
    });
    const payload = await res.json();
    const result = (payload.refresh_results || []).find((r) => r.provider === current);
    if (result && result.updated) {
      refreshStatusText = `Updated (${result.count})`;
    } else if (result) {
      refreshStatusText = `Failed (${result.error || "unknown"})`;
    } else {
      refreshStatusText = "No Update";
    }
  } catch (err) {
    refreshStatusText = "Failed";
  } finally {
    refreshBusy = false;
    refreshBtnInlineEl.disabled = false;
    refreshBtnInlineEl.textContent = "Refresh";
    refreshStatusInlineEl.textContent = refreshStatusText;
  }
  await refresh();
}

async function reloadConfig() {
  refreshBtnInlineEl.disabled = true;
  reloadBtn.disabled = true;
  refreshStatusText = "Reloading...";
  refreshStatusInlineEl.textContent = refreshStatusText;
  try {
    await fetch("/api/reload", { method: "POST" });
    refreshStatusText = "Reloaded";
    refreshStatusInlineEl.textContent = refreshStatusText;
  } catch (err) {
    refreshStatusText = "Reload Failed";
    refreshStatusInlineEl.textContent = refreshStatusText;
  } finally {
    refreshBtnInlineEl.disabled = false;
    reloadBtn.disabled = false;
  }
  previewProviderName = null;
  await refresh();
}

async function resetConfig() {
  refreshBtnInlineEl.disabled = true;
  reloadBtn.disabled = true;
  resetBtn.disabled = true;
  refreshStatusText = "Resetting...";
  refreshStatusInlineEl.textContent = refreshStatusText;
  try {
    await fetch("/api/reset", { method: "POST" });
    refreshStatusText = "Reset";
    refreshStatusInlineEl.textContent = refreshStatusText;
  } catch (err) {
    refreshStatusText = "Reset Failed";
    refreshStatusInlineEl.textContent = refreshStatusText;
  } finally {
    refreshBtnInlineEl.disabled = false;
    reloadBtn.disabled = false;
    resetBtn.disabled = false;
  }
  previewProviderName = null;
  await refresh();
}

async function refresh() {
  const state = await fetchState();
  const names = (state.providers || []).map((p) => p.name);
  if (!previewProviderName || !names.includes(previewProviderName)) {
    previewProviderName = state.selected_provider;
  }
  renderProviders(state);
  renderModels(state);
  renderHeaderOverrides(state);
  renderRequestOverrides(state);
  renderAuth(state);
}

reloadBtn.addEventListener("click", reloadConfig);
resetBtn.addEventListener("click", resetConfig);
refreshBtnInlineEl.addEventListener("click", refreshModels);
modelFilterInputEl.addEventListener("input", (event) => {
  modelFilterValue = event.target.value;
  refresh();
});
applyAuthBtn.addEventListener("click", () => {
  applyAuthOverride({
    token_in: tokenInEl.value,
    header_override: headerOverrideEl.value || undefined,
    request_override: requestOverrideEl.value || undefined,
    query_params: queryParamsEl.value || undefined,
    token_param: tokenParamEl.value || undefined,
    token_header: tokenHeaderEl.value || undefined,
    token_header_format: tokenHeaderFormatEl.value || undefined,
  });
});

presetClaudeCLIBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  // 选择第一个选项
  if (headerOverrideEl.options.length > 0) {
    headerOverrideEl.value = headerOverrideEl.options[0].value;
  }
  if (requestOverrideEl.options.length > 0) {
    requestOverrideEl.value = requestOverrideEl.options[0].value;
  }
  queryParamsEl.value = "beta=true";
  tokenHeaderEl.value = "Authorization";
  tokenHeaderFormatEl.value = "{token}";
});

presetDefaultBtn.addEventListener("click", () => {
  tokenInEl.value = "";
});

presetQueryBtn.addEventListener("click", () => {
  tokenInEl.value = "query";
  tokenParamEl.value = "token";
});

presetBearerBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  tokenHeaderEl.value = "Authorization";
  tokenHeaderFormatEl.value = "Bearer {token}";
});

presetDirectBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  tokenHeaderEl.value = "Authorization";
  tokenHeaderFormatEl.value = "{token}";
});

presetXApiBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  tokenHeaderEl.value = "x-api-key";
  tokenHeaderFormatEl.value = "{token}";
});

refresh().catch((err) => {
  console.error(err);
});
