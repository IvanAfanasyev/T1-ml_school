const API_BASE = getApiBase();
const CHAT_STORAGE_KEY = "cloudmatch.chat.v1";
const CATALOG_PAGE_SIZE = 100;

const sampleServices = [
  {
    service_id: "sample-postgresql",
    provider_id: "t1-cloud",
    provider_name: "Т1 Облако",
    name: "Managed Service for PostgreSQL",
    category: "Database",
    description: "Управляемая база данных PostgreSQL для production-нагрузок.",
    regions: ["Moscow", "Russia"],
    tech_stack_tags: ["postgresql"],
    price_from_rub: null,
    price_unit: null,
    pricing_items_count: 11,
    pricing_items: [],
    service_url: "https://t1-cloud.ru/",
  },
  {
    service_id: "sample-storage",
    provider_id: "selectel",
    provider_name: "Selectel",
    name: "Object Storage",
    category: "Storage",
    description: "S3-совместимое объектное хранилище для файлов, бэкапов и медиа.",
    regions: ["Moscow", "Saint-Petersburg"],
    tech_stack_tags: ["s3"],
    price_from_rub: null,
    price_unit: null,
    pricing_items_count: 8,
    pricing_items: [],
    service_url: "https://selectel.ru/",
  },
  {
    service_id: "sample-kubernetes",
    provider_id: "vk-cloud",
    provider_name: "VK Cloud",
    name: "Managed Kubernetes",
    category: "Containers",
    description: "Управляемые Kubernetes-кластеры для приложений и микросервисов.",
    regions: ["Russia"],
    tech_stack_tags: ["kubernetes"],
    price_from_rub: null,
    price_unit: null,
    pricing_items_count: 6,
    pricing_items: [],
    service_url: "https://cloud.vk.com/",
  },
];

const state = {
  activeTab: "storefront",
  chat: loadChatState(),
};

document.addEventListener("DOMContentLoaded", () => {
  bindTabs();
  bindChat();
  bindDialog();
  renderMessages();
  loadServices();
});

function getApiBase() {
  if (window.CLOUDMATCH_API_BASE !== undefined) {
    return String(window.CLOUDMATCH_API_BASE).replace(/\/$/, "");
  }

  const isLocalhost = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);

  if (window.location.protocol === "file:" || isLocalhost) {
    return "http://127.0.0.1:8000";
  }

  return "";
}

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

function bindTabs() {
  document.querySelectorAll("[data-tab-link]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      activateTab(button.dataset.tabLink);
    });
  });
}

function activateTab(tabName) {
  state.activeTab = tabName;

  document.querySelectorAll("[data-tab-link]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tabLink === tabName);
  });

  document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.tabPanel === tabName);
  });
}

async function loadServices() {
  const grid = document.getElementById("serviceGrid");
  grid.innerHTML = `<div class="loading-state">Загружаем витрину сервисов...</div>`;
  updateCatalogCount("Загрузка каталога...");

  try {
    const data = await fetchAllCatalogServices();
    updateCatalogCount(`Показано ${data.services.length} из ${data.total} сервисов`);
    renderServiceCards(data.services);
  } catch (error) {
    updateCatalogCount("Backend недоступен");
    renderServiceCards(sampleServices, {
      note: "Backend недоступен, поэтому показаны демонстрационные карточки.",
    });
  }
}

async function fetchAllCatalogServices() {
  const services = [];
  let offset = 0;
  let total = null;

  do {
    const response = await fetch(
      apiUrl(`/api/catalog/services?limit=${CATALOG_PAGE_SIZE}&offset=${offset}&pricing_limit=3`),
    );

    if (!response.ok) {
      throw new Error(`Catalog request failed: ${response.status}`);
    }

    const data = await response.json();
    const pageServices = data.services || [];
    total = Number(data.total || pageServices.length);
    services.push(...pageServices);

    if (!pageServices.length) {
      break;
    }

    offset += Number(data.limit || CATALOG_PAGE_SIZE);
  } while (services.length < total);

  return {
    total: total ?? services.length,
    services,
  };
}

function updateCatalogCount(text) {
  const counter = document.getElementById("catalogCount");

  if (counter) {
    counter.textContent = text;
  }
}

function renderServiceCards(services, options = {}) {
  const grid = document.getElementById("serviceGrid");

  if (!services.length) {
    grid.innerHTML = `<div class="empty-state">В каталоге пока нет сервисов для отображения.</div>`;
    return;
  }

  const note = options.note
    ? `<div class="empty-state">${escapeHtml(options.note)}</div>`
    : "";

  grid.innerHTML = `${note}${services.map(renderServiceCard).join("")}`;

  grid.querySelectorAll("[data-service-id]").forEach((cardButton) => {
    cardButton.addEventListener("click", () => {
      openServiceDialog(cardButton.dataset.serviceId);
    });
  });
}

function renderServiceCard(service) {
  const providerClass = getProviderClass(service.provider_id);
  const logoText = getProviderLogoText(service.provider_id, service.provider_name);
  const tags = [
    service.category,
    ...(service.regions || []).slice(0, 1),
    ...(service.tech_stack_tags || []).slice(0, 1),
  ].filter(Boolean);
  const serviceUrl = getServiceUrl(service);
  const serviceLink = serviceUrl
    ? `<a class="card-link" href="${escapeHtml(serviceUrl)}" target="_blank" rel="noreferrer">Сайт сервиса</a>`
    : `<span class="card-link is-disabled">Ссылка недоступна</span>`;

  return `
    <article class="service-card">
      <div class="provider-art">
        <div class="logo-mark ${providerClass}">${escapeHtml(logoText)}</div>
      </div>
      <div class="card-body">
        <p class="provider-name">${escapeHtml(service.provider_name || service.provider_id || "Provider")}</p>
        <h2 class="service-name">${escapeHtml(service.name || "Cloud service")}</h2>
        <p class="service-description">${escapeHtml(service.description || "Описание сервиса будет доступно в карточке.")}</p>
        <div class="card-meta">
          ${tags.map((tag) => `<span class="meta-pill">${escapeHtml(tag)}</span>`).join("")}
        </div>
        <div class="price-row">
          <span>${formatTariffCount(service.pricing_items_count)}</span>
          <strong>${formatPrice(service.price_from_rub, service.price_unit)}</strong>
        </div>
        <div class="card-actions">
          <button class="details-button" type="button" data-service-id="${escapeHtml(service.service_id)}">Подробнее</button>
          ${serviceLink}
        </div>
      </div>
    </article>
  `;
}

async function openServiceDialog(serviceId) {
  const dialog = document.getElementById("serviceDialog");
  const content = document.getElementById("dialogContent");
  content.innerHTML = `<div class="dialog-card"><p>Загружаем карточку сервиса...</p></div>`;
  dialog.showModal();

  try {
    const response = await fetch(
      apiUrl(`/api/catalog/services/${encodeURIComponent(serviceId)}?pricing_limit=8`),
    );

    if (!response.ok) {
      throw new Error(`Service request failed: ${response.status}`);
    }

    const service = await response.json();
    content.innerHTML = renderDialogContent(service);
  } catch (error) {
    const service = sampleServices.find((item) => item.service_id === serviceId);
    content.innerHTML = renderDialogContent(service || sampleServices[0]);
  }
}

function renderDialogContent(service) {
  const pricingItems = service.pricing_items || [];
  const serviceUrl = getServiceUrl(service);
  const serviceLink = serviceUrl
    ? `<a class="primary-link" href="${escapeHtml(serviceUrl)}" target="_blank" rel="noreferrer">Открыть сайт сервиса</a>`
    : "";
  const pricingHtml = pricingItems.length
    ? pricingItems.map(renderPricingItem).join("")
    : `<div class="pricing-item"><span>Тарифные позиции</span><strong>Нет данных</strong></div>`;

  return `
    <div class="dialog-card">
      <p class="eyebrow">${escapeHtml(service.provider_name || service.provider_id || "Provider")}</p>
      <h2>${escapeHtml(service.name || "Cloud service")}</h2>
      <p>${escapeHtml(service.description || "Описание сервиса отсутствует.")}</p>
      <div class="card-meta">
        ${(service.regions || []).slice(0, 3).map((region) => `<span class="meta-pill">${escapeHtml(region)}</span>`).join("")}
        ${(service.tech_stack_tags || []).slice(0, 3).map((tag) => `<span class="meta-pill">${escapeHtml(tag)}</span>`).join("")}
      </div>
      ${serviceLink}
      <div class="pricing-list">${pricingHtml}</div>
    </div>
  `;
}

function renderPricingItem(item) {
  return `
    <div class="pricing-item">
      <span>${escapeHtml(item.item_name || item.item_type || "Тарифная позиция")}</span>
      <strong>${formatPrice(item.price_rub, item.price_unit)}</strong>
    </div>
  `;
}

function bindDialog() {
  const dialog = document.getElementById("serviceDialog");
  document.getElementById("dialogClose").addEventListener("click", () => {
    dialog.close();
  });
}

function bindChat() {
  const input = document.getElementById("promptInput");

  document.getElementById("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = input.value.trim();

    if (!message) {
      return;
    }

    input.value = "";
    appendMessage("user", message);
    await sendChatMessage(message);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }

    if (event.metaKey || event.ctrlKey) {
      event.preventDefault();
      insertTextareaText(input, "\n");
      return;
    }

    if (event.shiftKey) {
      return;
    }

    event.preventDefault();
    document.getElementById("chatForm").requestSubmit();
  });

  document.getElementById("clearChatButton").addEventListener("click", () => {
    localStorage.removeItem(CHAT_STORAGE_KEY);
    state.chat = createEmptyChatState();
    renderMessages();
    input.focus();
  });
}

async function sendChatMessage(message) {
  const button = document.querySelector(".send-button");
  button.disabled = true;

  try {
    const response = await fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: "local-user",
        chat_id: state.chat.chat_id,
        message,
        memory: state.chat.memory,
        with_explanation: true,
        include_debug: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.status}`);
    }

    const data = await response.json();
    state.chat.memory = data.memory;
    const assistantMessage = buildAssistantMessage(data);
    appendMessage(
      "assistant",
      assistantMessage.text,
      getAssistantMessageVariant(data),
      assistantMessage.html,
    );
  } catch (error) {
    appendMessage(
      "assistant",
      "Не удалось получить ответ backend. Проверьте, что FastAPI запущен и доступен.",
    );
  } finally {
    saveChatState();
    button.disabled = false;
  }
}

function buildAssistantMessage(data) {
  if (data.action === "search" && data.search?.answer) {
    return {
      text: data.search.answer,
      html: buildSearchResponseHtml(data.search),
    };
  }

  if (data.clarification_questions?.length) {
    return {
      text: `${data.message}\n\n${data.clarification_questions.map((question) => `• ${question}`).join("\n")}`,
      html: buildClarificationHtml(data),
    };
  }

  return {
    text: data.message || "Ответ получен.",
    html: buildPlainAssistantHtml(data.message || "Ответ получен."),
  };
}

function getAssistantMessageVariant(data) {
  if (data.action === "search" && data.search?.answer) {
    return "search-answer";
  }

  if (data.needs_clarification) {
    return "clarification-answer";
  }

  return "";
}

function appendMessage(role, content, variant = "", html = "") {
  state.chat.messages.push({ role, content, variant, html });
  saveChatState();
  renderMessages();
}

function renderMessages() {
  const messages = document.getElementById("messages");
  const items = state.chat.messages.length
    ? state.chat.messages
    : [
        {
          role: "assistant",
          content:
            "Опишите задачу: база данных, Kubernetes, object storage, backend или другой облачный сценарий.",
        },
      ];

  messages.innerHTML = items
    .map(
      (message) => `
        <div class="message ${message.role} ${message.variant || ""}">
          ${renderMessageContent(message)}
        </div>
      `,
    )
    .join("");
  messages.scrollTop = messages.scrollHeight;
}

function loadChatState() {
  try {
    const saved = JSON.parse(localStorage.getItem(CHAT_STORAGE_KEY));

    if (saved && Array.isArray(saved.messages)) {
      return saved;
    }
  } catch (error) {
    localStorage.removeItem(CHAT_STORAGE_KEY);
  }

  return createEmptyChatState();
}

function createEmptyChatState() {
  return {
    chat_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    messages: [],
    memory: null,
  };
}

function saveChatState() {
  localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(state.chat));
}

function getProviderClass(providerId = "") {
  const normalized = providerId.toLowerCase();

  if (normalized.includes("selectel")) {
    return "provider-selectel";
  }

  if (normalized.includes("t1")) {
    return "provider-t1-cloud";
  }

  if (normalized.includes("vk")) {
    return "provider-vk-cloud";
  }

  if (normalized.includes("cloud-ru")) {
    return "provider-cloud-ru";
  }

  return "provider-default";
}

function getProviderLogoText(providerId = "", providerName = "") {
  const source = `${providerId} ${providerName}`.toLowerCase();

  if (source.includes("selectel")) {
    return "SEL";
  }

  if (source.includes("t1")) {
    return "T1";
  }

  if (source.includes("vk")) {
    return "VK";
  }

  if (source.includes("cloud.ru") || source.includes("cloud-ru")) {
    return "CLOUD";
  }

  return (providerName || providerId || "CM").slice(0, 3).toUpperCase();
}

function formatTariffCount(count) {
  const value = Number(count || 0);
  return `${value} тарифных позиций`;
}

function formatPrice(price, unit) {
  if (price === null || price === undefined) {
    return "Цена уточняется";
  }

  const formatted = new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 6,
  }).format(Number(price));

  return unit ? `от ${formatted} ${unit}` : `от ${formatted} ₽`;
}

function getServiceUrl(service) {
  const url = service.service_url || service.source_url;

  if (!url) {
    return "";
  }

  return String(url).startsWith("http") ? String(url) : "";
}

function insertTextareaText(textarea, text) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const value = textarea.value;
  textarea.value = `${value.slice(0, start)}${text}${value.slice(end)}`;
  textarea.selectionStart = start + text.length;
  textarea.selectionEnd = start + text.length;
}

function renderMessageContent(message) {
  if (message.role === "assistant" && message.html) {
    return message.html;
  }

  const rawContent = String(message.content || "").trim();
  const content = escapeHtml(rawContent);

  if (message.role !== "assistant") {
    return content;
  }

  return buildPlainAssistantHtml(rawContent);
}

function buildPlainAssistantHtml(text) {
  const lines = String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) {
    return "";
  }

  const blocks = [];
  let listItems = [];

  const flushList = () => {
    if (!listItems.length) {
      return;
    }

    blocks.push(
      `<ul class="assistant-list">${listItems.map((item) => `<li>${linkifyEscapedText(escapeHtml(item))}</li>`).join("")}</ul>`,
    );
    listItems = [];
  };

  lines.forEach((line) => {
    const bullet = line.match(/^[-•]\s+(.+)$/);

    if (bullet) {
      listItems.push(bullet[1]);
      return;
    }

    flushList();
    blocks.push(`<p>${linkifyEscapedText(escapeHtml(line))}</p>`);
  });

  flushList();

  return `<div class="assistant-block plain-message">${blocks.join("")}</div>`;
}

function buildClarificationHtml(data) {
  const questions = data.clarification_questions || [];

  return `
    <div class="assistant-block">
      <p>${escapeHtml(data.message || "Нужно уточнить несколько параметров.")}</p>
      <ul class="assistant-list">
        ${questions.map((question) => `<li>${escapeHtml(question)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function buildSearchResponseHtml(search) {
  const query = search.structured_query || {};
  const components = query.required_components || [];
  const results = search.results || [];
  const isBundle = results.some((result) => result.solution_component_rank);
  const fallbackSummary = isBundle
    ? buildBundleFallbackSummary(results)
    : buildSimpleFallbackSummary(results);

  return `
    <div class="answer-layout">
      <section class="answer-section">
        <h2>Рекомендации</h2>
        <p>${escapeHtml(cleanUserText(search.summary || fallbackSummary))}</p>
      </section>

      <section class="answer-section">
        <h3>Как я понял задачу</h3>
        <div class="answer-chips">
          ${buildQueryChips(query)}
        </div>
      </section>

      ${
        components.length > 1
          ? `
            <section class="answer-section">
              <h3>Нужная связка</h3>
              <ol class="component-list">
                ${components.map((component) => `<li>${escapeHtml(formatComponentLabel(component))}</li>`).join("")}
              </ol>
            </section>
          `
          : ""
      }

      <section class="answer-section">
        <h3>${isBundle ? "Подобранные связки провайдеров" : "Top-3 провайдера"}</h3>
        ${buildRecommendationContent(results)}
      </section>
    </div>
  `;
}

function buildRecommendationContent(results) {
  if (!results.length) {
    return `<div class="empty-state compact">Подходящие сервисы не найдены.</div>`;
  }

  const isBundle = results.some((result) => result.solution_component_rank);

  if (!isBundle) {
    return `
      <div class="recommendation-list">
        ${results.map((result) => buildRecommendationCard(result, { compact: false, providerMode: true })).join("")}
      </div>
    `;
  }

  const grouped = results.reduce((acc, result) => {
    const rank = Number(result.solution_component_rank || result.rank || 1);
    acc[rank] = acc[rank] || [];
    acc[rank].push(result);
    return acc;
  }, {});

  return `
    <div class="bundle-list">
      ${Object.keys(grouped)
        .map(Number)
        .sort((a, b) => a - b)
        .map((rank) => buildBundleCard(rank, grouped[rank]))
        .join("")}
    </div>
  `;
}

function buildBundleCard(rank, results) {
  const title = results
    .map((result) => `${result.provider_name} — ${result.service_name}`)
    .join(" + ");
  const roles = results.map((result) => formatComponentShortTitle(result.solution_component)).join(", ");
  const intro =
    rank === 1
      ? "Эта связка собрана из сервисов одного провайдера, чтобы компоненты проще было внедрять и сопровождать вместе."
      : "Это альтернативная связка от одного провайдера для тех же частей задачи.";

  return `
    <article class="bundle-card">
      <div class="bundle-head">
        <span>#${rank}</span>
        <h4>${escapeHtml(title)}</h4>
      </div>
      <p>${escapeHtml(`${intro} Она закрывает роли: ${roles}.`)}</p>
      <div class="bundle-items">
        ${results.map((result) => buildRecommendationCard(result, { compact: true })).join("")}
      </div>
    </article>
  `;
}

function buildBundleFallbackSummary(results) {
  const groupCount = new Set(
    results
      .filter((result) => result.solution_component_rank)
      .map((result) => Number(result.solution_component_rank)),
  ).size;

  if (groupCount > 0 && groupCount < 3) {
    return `Запрос состоит из нескольких инфраструктурных частей. В текущих данных найдено ${groupCount} связк(и), которые закрывают обязательные роли вместе. Остальные провайдеры не попали в список, потому что не закрывают полный набор компонентов, регион или обязательные требования.`;
  }

  return "Запрос разбит на отдельные инфраструктурные роли, и для каждой роли подобраны свои кандидаты.";
}

function buildSimpleFallbackSummary(results) {
  const hasOnlyOverBudget = results.length > 0 && results.every((result) => {
    const status = result.matched_entities?.budget_status;
    return status === "over_budget" || status === "slightly_over_budget";
  });

  if (hasOnlyOverBudget) {
    return "Точных вариантов в указанном бюджете не найдено. Ниже показаны ближайшие провайдеры из каталога, но цену по ним нужно проверять отдельно.";
  }

  return "Я подобрал top-3 провайдера и показал сервис, который лучше всего представляет каждого из них для этой задачи.";
}
function buildQueryChips(query) {
  const constraints = query.constraints || {};
  const chips = [];

  if (query.tech_stack?.length) {
    chips.push(`Технологии: ${query.tech_stack.join(", ")}`);
  }

  if (query.use_case?.length) {
    chips.push(`Сценарии: ${query.use_case.join(", ")}`);
  }

  if (constraints.region) {
    chips.push(`Регион: ${constraints.region}`);
  }

  if (constraints.budget_max !== null && constraints.budget_max !== undefined) {
    chips.push(`Бюджет: до ${formatNumber(constraints.budget_max)} руб./мес`);
  }

  if (constraints.compliance_tags?.length) {
    chips.push(`Соответствие: ${constraints.compliance_tags.join(", ")}`);
  }

  if (!chips.length) {
    chips.push("Параметры явно не выделены");
  }

  return chips.map((chip) => `<span>${escapeHtml(chip)}</span>`).join("");
}

function buildRecommendationCard(result, options = {}) {
  const url = getServiceUrl(result);
  const matched = formatMatchedEntities(result.matched_entities || {});
  const missing = formatMissingEntities(result.matched_entities || {});
  const label = result.solution_component
    ? formatComponentShortTitle(result.solution_component)
    : `#${result.rank}`;
  const title = options.providerMode
    ? `${result.provider_name}`
    : `${result.provider_name} — ${result.service_name}`;
  const rankReason = buildRankReason(result, matched, missing);
  const tag = options.compact ? "div" : "article";

  return `
    <${tag} class="recommendation-card ${options.compact ? "is-compact" : ""}">
      <div class="recommendation-topline">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(title)}</strong>
      </div>
      ${
        options.providerMode
          ? `<p class="recommendation-role">Релевантный сервис: ${escapeHtml(result.service_name)}</p>`
          : ""
      }
      ${
        result.solution_component_reason
          ? `<p class="recommendation-role">${escapeHtml(result.solution_component_reason)}</p>`
          : ""
      }
      <dl class="recommendation-meta">
        <div>
          <dt>Категория</dt>
          <dd>${escapeHtml(result.category || "Не указана")}</dd>
        </div>
        <div>
          <dt>Цена</dt>
          <dd>${escapeHtml(formatPrice(result.price_from_rub, result.price_unit))}</dd>
        </div>
      </dl>
      ${matched ? `<p><strong>Совпало:</strong> ${escapeHtml(matched)}</p>` : ""}
      ${missing ? `<p><strong>Проверить отдельно:</strong> ${escapeHtml(missing)}</p>` : ""}
      <p class="rank-reason">${escapeHtml(rankReason)}</p>
      ${result.explanation ? `<p>${escapeHtml(cleanUserText(result.explanation))}</p>` : ""}
      ${
        url
          ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Открыть сайт сервиса</a>`
          : ""
      }
    </${tag}>
  `;
}

function buildRankReason(result, matched, missing) {
  const base = result.solution_component
   ? `Этот сервис выбран для роли «${formatComponentShortTitle(result.solution_component)}», потому что в данных есть совпадения с этой частью задачи.`
    : `Провайдер представлен этим сервисом, потому что в данных есть совпадения с запросом пользователя.`;
  const matchedPart = matched ? ` Сильные совпадения: ${matched}.` : "";
  const missingPart = missing ? ` Отдельно проверить: ${missing}.` : "";

  return `${base}${matchedPart}${missingPart}`;
}

function formatMatchedEntities(matched) {
  const parts = [];

  if (matched.matched_tech_stack?.length) {
    parts.push(formatEntityValues(matched.matched_tech_stack));
  }

  if (matched.matched_use_case?.length) {
    parts.push(formatEntityValues(matched.matched_use_case));
  }

  if (matched.matched_components?.length) {
    parts.push(formatEntityValues(matched.matched_components));
  }

  if (matched.matched_requirements?.length) {
    parts.push(formatEntityValues(matched.matched_requirements));
  }

  if (matched.matched_region) {
    parts.push(`регион ${matched.matched_region}`);
  }

  if (matched.budget_status === "within_budget") {
    parts.push("укладывается в бюджет");
  }

  if (matched.budget_status === "slightly_over_budget") {
    parts.push("близко к бюджету");
  }

  return parts.join("; ");
}

function formatMissingEntities(matched) {
  const parts = [];

  if (matched.missing_tech_stack?.length) {
    parts.push(formatEntityValues(matched.missing_tech_stack));
  }

  if (matched.missing_use_case?.length) {
    parts.push(formatEntityValues(matched.missing_use_case));
  }

  if (matched.missing_components?.length) {
    parts.push(formatEntityValues(matched.missing_components));
  }

  if (matched.missing_requirements?.length) {
    parts.push(formatEntityValues(matched.missing_requirements));
  }

  if (matched.budget_status === "price_unknown") {
    parts.push("цена не определена");
  }

  if (matched.budget_status === "over_budget") {
    parts.push("выше бюджета");
  }

  if (matched.budget_status === "slightly_over_budget") {
    parts.push("может немного превышать бюджет");
  }

  return parts.join("; ");
}

function formatEntityValues(values) {
  return values.map(humanizeEntityValue).join(", ");
}

function humanizeEntityValue(value) {
  const text = String(value || "");
  const lower = text.toLowerCase();

  if (lower.startsWith("scalability=")) {
    return "быстрое масштабирование";
  }

  if (lower === "billing_period=month") {
    return "помесячная тарификация";
  }

  if (lower === "billing_period=hour") {
    return "почасовая тарификация";
  }

  if (lower.startsWith("budget_max=")) {
    const amount = text.split("=").slice(1).join("=");
    return `бюджет до ${amount} руб.`;
  }

  return text.replaceAll("_", " ");
}

function formatComponentLabel(component) {
  const componentName = component.component;
  const labels = {
    compute: "Compute / Virtual Machine / App runtime",
    managed_database: "Managed database",
    object_storage: "Object Storage / S3",
    backup: "Backup",
    kubernetes: "Managed Kubernetes",
    load_balancer: "Load Balancer",
    analytics: "Analytics",
    ai_ml: "AI / ML",
  };
  let title = labels[componentName] || String(componentName || "Компонент").replaceAll("_", " ");

  if (component.db_engine) {
    title += ` (${component.db_engine})`;
  } else if (component.subtype) {
    title += ` (${component.subtype})`;
  }

  return component.reason ? `${title} — ${component.reason}` : title;
}

function formatComponentShortTitle(component) {
  const labels = {
    compute: "Backend",
    managed_database: "Database",
    object_storage: "Storage",
    backup: "Backup",
    kubernetes: "Kubernetes",
    load_balancer: "Balancer",
    analytics: "Analytics",
    ai_ml: "AI / ML",
  };

  return labels[component] || component.replaceAll("_", " ");
}

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function linkifyEscapedText(text) {
  return text.replace(
    /(https?:\/\/[^\s<]+)/g,
    (url) => `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`,
  );
}

function cleanUserText(text) {
  return String(text || "")
    .replaceAll("final_score", "релевантность")
    .replaceAll("retrieval_score", "релевантность")
    .replaceAll("entity_match_score", "совпадение требований")
    .replaceAll("embedding_score", "релевантность")
    .replaceAll("bm25_score", "текстовое совпадение")
    .replaceAll("score", "релевантность");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
