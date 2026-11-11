/**
 * Utilidades puras de A2UI compartidas por el renderer y las pruebas de Node.
 * No contienen JSX para poder probarse con `node --test` sin transpilación.
 */

const money = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  maximumFractionDigits: 2,
});

export const UIPLAN_COMPONENTS = [
  "StatCard",
  "BarChart",
  "Table",
  "ProgressRing",
  "TransferForm",
];

export function formatMoney(value) {
  return money.format(Number(value) || 0);
}

/**
 * Convierte el botón del TransferForm en el mensaje y, cuando el servidor ya
 * emitió los datos de confirmación, en el evento tipado que ejecuta el abono
 * por la ruta de confirmación (nunca una escritura directa desde el cliente).
 */
export function transferFormAction(component) {
  const message =
    `Confirmo el abono de ${formatMoney(component.amount)} a ${component.to_account}.`;
  if (
    Number.isInteger(component.goal_id) &&
    typeof component.confirmation_token === "string" &&
    component.confirmation_token.length >= 36 &&
    typeof component.idempotency_key === "string" &&
    component.idempotency_key.length === 36
  ) {
    return {
      message,
      event: {
        type: "savings_contribution_confirmed",
        payload: {
          goal_id: component.goal_id,
          amount: component.amount,
          confirmation_token: component.confirmation_token,
          idempotency_key: component.idempotency_key,
        },
      },
    };
  }
  return { message, event: null };
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function componentErrors(component, index) {
  const path = `components[${index}]`;
  if (!component || typeof component !== "object") {
    return [`${path}: no es un objeto`];
  }
  if (!UIPLAN_COMPONENTS.includes(component.type)) {
    return [`${path}: tipo no permitido`];
  }
  const errors = [];
  if (!isNonEmptyString(component.title)) errors.push(`${path}.title`);
  if (component.type === "StatCard") {
    if (!isNonEmptyString(component.value)) errors.push(`${path}.value`);
  } else if (component.type === "BarChart") {
    if (!Array.isArray(component.series) || component.series.length === 0) {
      errors.push(`${path}.series`);
    } else {
      component.series.forEach((item, itemIndex) => {
        if (!isNonEmptyString(item?.label) || typeof item?.value !== "number") {
          errors.push(`${path}.series[${itemIndex}]`);
        }
      });
    }
  } else if (component.type === "Table") {
    if (!Array.isArray(component.columns) || component.columns.length === 0) {
      errors.push(`${path}.columns`);
    }
    if (!Array.isArray(component.rows)) {
      errors.push(`${path}.rows`);
    } else if (
      Array.isArray(component.columns) &&
      component.rows.some((row) => !Array.isArray(row) || row.length !== component.columns.length)
    ) {
      errors.push(`${path}.rows: ancho distinto a columns`);
    }
  } else if (component.type === "ProgressRing") {
    if (!isNonEmptyString(component.label)) errors.push(`${path}.label`);
    if (typeof component.value !== "number" || component.value < 0 || component.value > 100) {
      errors.push(`${path}.value`);
    }
  } else if (component.type === "TransferForm") {
    if (!isNonEmptyString(component.from_account)) errors.push(`${path}.from_account`);
    if (!isNonEmptyString(component.to_account)) errors.push(`${path}.to_account`);
    if (typeof component.amount !== "number" || component.amount <= 0) {
      errors.push(`${path}.amount`);
    }
    if (!isNonEmptyString(component.concept)) errors.push(`${path}.concept`);
    if (!isNonEmptyString(component.confirmation_text)) {
      errors.push(`${path}.confirmation_text`);
    }
  }
  return errors;
}

/**
 * Comprueba la forma mínima de un ui_plan antes de renderizarlo. Las props
 * opcionales pueden faltar; las requeridas no.
 */
export function validateUIPlanShape(plan) {
  const errors = [];
  if (!plan || typeof plan !== "object") {
    return { ok: false, errors: ["plan: no es un objeto"] };
  }
  if (!isNonEmptyString(plan.title)) errors.push("title");
  if (!Array.isArray(plan.components) || plan.components.length === 0) {
    errors.push("components");
  } else {
    plan.components.forEach((component, index) => {
      errors.push(...componentErrors(component, index));
    });
  }
  return { ok: errors.length === 0, errors };
}
