const stateUrl = "/api/state";
const selectUrl = "/api/select";
const refreshUrl = "/api/refresh-models";
const authUrl = "/api/provider-auth";

let globalEnvModels = {};

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
const presetOpenAIBtn = document.getElementById("presetOpenAI");
const presetDefaultBtn = document.getElementById("presetDefault");
const presetQueryBtn = document.getElementById("presetQuery");
const presetBearerBtn = document.getElementById("presetBearer");
const presetDirectBtn = document.getElementById("presetDirect");
const presetXApiBtn = document.getElementById("presetXApi");
const reloadBtn = document.getElementById("reloadBtn");
const refreshAndTestBtn = document.getElementById("refreshAndTestBtn");
const retestFailedBtn = document.getElementById("retestFailedBtn");
const resetOverrideBtn = document.getElementById("resetOverride");
const testModelEl = document.getElementById("testModel");
const testPromptEl = document.getElementById("testPrompt");
const testBtn = document.getElementById("testBtn");

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

function extractBaseUrl(apiBaseUrl) {
  if (apiBaseUrl.includes("/anthropic/v1/messages")) {
    return apiBaseUrl.replace("/anthropic/v1/messages", "");
  }
  if (apiBaseUrl.includes("/v1/chat/completions")) {
    return apiBaseUrl.replace("/v1/chat/completions", "");
  }
  if (apiBaseUrl.includes("/v1/messages")) {
    return apiBaseUrl.replace("/v1/messages", "");
  }
  return apiBaseUrl.replace(/\/$/, "");
}

function extractDomain(apiBaseUrl) {
  // 从 api_base_url 中提取 https://domain/ 部分
  const baseUrl = extractBaseUrl(apiBaseUrl);
  const parts = baseUrl.split('/');
  if (parts.length >= 3) {
    return `${parts[0]}//${parts[2]}`;
  }
  return baseUrl;
}

function getCheckinUrl(provider) {
  // 如果 provider 有 checkin 属性且不为空，使用它
  if (provider.checkin && provider.checkin.trim()) {
    return provider.checkin;
  }
  // 否则，从 api_base_url 提取 domain，返回 https://domain/console/personal
  const domain = extractDomain(provider.api_base_url || "");
  return `${domain}/console/personal`;
}

async function copySettings(provider) {
  const baseUrl = extractBaseUrl(provider.api_base_url || "");
  const apiKey = provider.api_key || "";

  // 构建 env 配置
  const env = {
    "ANTHROPIC_AUTH_TOKEN": apiKey,
    "ANTHROPIC_BASE_URL": baseUrl
  };

  // 合并 env-models 配置
  // 优先级：provider 级别 > 全局级别
  const envModels = {};
  if (globalEnvModels && Object.keys(globalEnvModels).length > 0) {
    Object.assign(envModels, globalEnvModels);
  }
  if (provider["env-models"] && Object.keys(provider["env-models"]).length > 0) {
    Object.assign(envModels, provider["env-models"]);
  }

  // 将 env-models 添加到 env
  if (Object.keys(envModels).length > 0) {
    Object.assign(env, envModels);
  }

  const settings = {
    "env": env,
    "includeCoAuthoredBy": false
  };

  const text = JSON.stringify(settings, null, 2);
  await copyText(text);
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
    const fullName = provider.name || "Unnamed";
    const displayName = fullName.length > 8 ? fullName.substring(0, 8) : fullName;
    name.textContent = displayName;
    if (provider.test_result === true) {
      name.classList.add("test-success");
    } else {
      name.classList.add("test-default");
    }

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

    const copySettingsBtn = document.createElement("button");
    copySettingsBtn.className = "mini-btn";
    copySettingsBtn.textContent = "settings.json";
    copySettingsBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      copySettings(provider);
    });

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

    const checkinBtn = document.createElement("button");
    checkinBtn.className = "mini-btn";
    checkinBtn.textContent = "签到";
    checkinBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      const checkinUrl = getCheckinUrl(provider);
      window.open(checkinUrl, "_blank");
    });

    actions.appendChild(checkinBtn);
    actions.appendChild(copySettingsBtn);
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
  tokenInEl.value = override.token_in !== undefined ? override.token_in : "";
  headerOverrideEl.value = override.header_override || "";
  requestOverrideEl.value = override.request_override || "";
  queryParamsEl.value = override.query_params || "";
  tokenParamEl.value = override.token_param || "";
  tokenHeaderEl.value = override.token_header || "";
  tokenHeaderFormatEl.value = override.token_header_format || "";
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

async function refresh() {
  const state = await fetchState();
  globalEnvModels = state.global_env_models || {};
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
refreshAndTestBtn.addEventListener("click", async () => {
  const prompt = testPromptEl.value || "当前项目如何构建为Docker版本";

  // 如果输入框为空，填充实际使用的默认值
  if (!testPromptEl.value) {
    testPromptEl.value = prompt;
  }

  refreshAndTestBtn.disabled = true;
  refreshAndTestBtn.textContent = "Running...";
  try {
    await fetch("/api/refresh-and-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
  } catch (err) {
    console.error("Refresh & Test error:", err);
  } finally {
    refreshAndTestBtn.disabled = false;
    refreshAndTestBtn.textContent = "Refresh & Test All";
  }
  await refresh();
});
retestFailedBtn.addEventListener("click", async () => {
  const prompt = testPromptEl.value || "当前项目如何构建为Docker版本";

  // 如果输入框为空，填充实际使用的默认值
  if (!testPromptEl.value) {
    testPromptEl.value = prompt;
  }

  retestFailedBtn.disabled = true;
  retestFailedBtn.textContent = "Running...";
  try {
    await fetch("/api/retest-failed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
  } catch (err) {
    console.error("Retest Failed error:", err);
  } finally {
    retestFailedBtn.disabled = false;
    retestFailedBtn.textContent = "Retest Failed";
  }
  await refresh();
});
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

presetOpenAIBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  // 选择第二个选项（CherryStudio 和 OpenAI）
  if (headerOverrideEl.options.length > 1) {
    headerOverrideEl.value = headerOverrideEl.options[1].value;
  }
  if (requestOverrideEl.options.length > 1) {
    requestOverrideEl.value = requestOverrideEl.options[1].value;
  }
  queryParamsEl.value = "";
  tokenHeaderEl.value = "Authorization";
  tokenHeaderFormatEl.value = "{token}";
});

presetDefaultBtn.addEventListener("click", () => {
  tokenInEl.value = "";
  // 清空所有字段
  tokenParamEl.value = "";
  tokenHeaderEl.value = "";
  tokenHeaderFormatEl.value = "";
});

presetQueryBtn.addEventListener("click", () => {
  tokenInEl.value = "query";
  tokenParamEl.value = "token";
  // 清空 header 相关字段
  tokenHeaderEl.value = "";
  tokenHeaderFormatEl.value = "";
});

presetBearerBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  tokenHeaderEl.value = "Authorization";
  tokenHeaderFormatEl.value = "Bearer {token}";
  // 清空 query 相关字段
  tokenParamEl.value = "";
});

presetDirectBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  tokenHeaderEl.value = "Authorization";
  tokenHeaderFormatEl.value = "{token}";
  // 清空 query 相关字段
  tokenParamEl.value = "";
});

presetXApiBtn.addEventListener("click", () => {
  tokenInEl.value = "header";
  tokenHeaderEl.value = "x-api-key";
  tokenHeaderFormatEl.value = "{token}";
  // 清空 query 相关字段
  tokenParamEl.value = "";
});

resetOverrideBtn.addEventListener("click", () => {
  applyAuthOverride({});
});

testBtn.addEventListener("click", async () => {
  const state = await fetchState();
  const provider = state.selected_provider;
  if (!provider) return;
  const model = testModelEl.value || "claude-haiku-4-5-20251001";
  const prompt = testPromptEl.value || "当前项目如何构建为Docker版本";

  // 如果输入框为空，填充实际使用的默认值
  if (!testModelEl.value) {
    testModelEl.value = model;
  }
  if (!testPromptEl.value) {
    testPromptEl.value = prompt;
  }

  testBtn.disabled = true;
  testBtn.textContent = "Testing...";
  try {
    await fetch("/api/test-provider", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, model, prompt }),
    });
  } catch (err) {
    console.error("Test error:", err);
  } finally {
    testBtn.disabled = false;
    testBtn.textContent = "Test";
  }
  await refresh();
});

refresh().catch((err) => {
  console.error(err);
});
