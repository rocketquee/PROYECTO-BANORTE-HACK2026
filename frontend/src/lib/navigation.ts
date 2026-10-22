export type ViewId =
  | "inicio" | "dashboard" | "asistente" | "cuentas" | "movimientos" | "tarjetas"
  | "pagos" | "contactos" | "creditos" | "ahorro" | "inversiones"
  | "seguros" | "presupuesto" | "notificaciones" | "perfil" | "ayuda";

export const NAV_ITEMS: { id: ViewId; label: string; icon: string; group: "principal" | "productos" | "soporte" }[] = [
  { id: "inicio", label: "Inicio", icon: "M3 10.5 12 3l9 7.5M5 9v12h14V9m-9 12v-7h4v7", group: "principal" },
  { id: "asistente", label: "Asistente", icon: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z", group: "principal" },
  { id: "dashboard", label: "Resumen", icon: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z", group: "principal" },
  { id: "movimientos", label: "Movimientos", icon: "M4 6h16M4 12h16M4 18h10", group: "principal" },
  { id: "presupuesto", label: "Presupuesto", icon: "M12 8v8m-4-4h8M3 12a9 9 0 1018 0 9 9 0 00-18 0z", group: "principal" },
  { id: "ahorro", label: "Metas", icon: "M12 3v2m0 14v2M5 12H3m18 0h-2M6.3 6.3L4.9 4.9m12.8 1.4l1.4-1.4M7 17a5 5 0 1110 0 5 5 0 01-10 0z", group: "principal" },
  { id: "tarjetas", label: "Tarjetas", icon: "M2 8h20M2 6a2 2 0 012-2h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2z", group: "principal" },
  { id: "cuentas", label: "Mis cuentas", icon: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6", group: "productos" },
  { id: "pagos", label: "Pagos y transferencias", icon: "M7 10h10M7 14h4m9-2a9 9 0 11-18 0 9 9 0 0118 0z", group: "productos" },
  { id: "creditos", label: "Créditos y simulador", icon: "M12 2v20m5-15H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6", group: "productos" },
  { id: "inversiones", label: "Inversiones", icon: "M3 17l6-6 4 4 8-8M14 7h7v7", group: "productos" },
  { id: "seguros", label: "Seguros", icon: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z", group: "productos" },
  { id: "notificaciones", label: "Notificaciones", icon: "M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 00-4-5.7V5a2 2 0 10-4 0v.3A6 6 0 006 11v3.2a2 2 0 01-.6 1.4L4 17h11zm-3 4a2 2 0 002-2h-4a2 2 0 002 2z", group: "soporte" },
  { id: "perfil", label: "Perfil y preferencias", icon: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM4 21a8 8 0 0116 0", group: "soporte" },
  { id: "ayuda", label: "Ayuda y seguridad", icon: "M12 17h.01M12 14a2.5 2.5 0 10-2.5-2.5M12 21a9 9 0 110-18 9 9 0 010 18z", group: "soporte" },
];

export const VIEW_META: Record<ViewId, { title: string; description: string; question: string }> = {
  inicio: {
    title: "Inicio",
    description: "Tu tarjeta de demostración y controles, en un solo lugar.",
    question: "Dame un resumen de mis finanzas",
  },
  dashboard: {
    title: "Resumen financiero",
    description: "Una vista clara de tus cuentas, gastos y metas. Datos ficticios para este prototipo.",
    question: "Dame un resumen de mis finanzas",
  },
  asistente: {
    title: "Asistente financiero",
    description: "Revisa tus gastos, ahorro, créditos y presupuesto con datos de demostración.",
    question: "Ayúdame a entender mis finanzas",
  },
  cuentas: {
    title: "Mis cuentas",
    description: "Saldos de tus cuentas en este prototipo.",
    question: "¿Cuál es el saldo de mis cuentas?",
  },
  movimientos: {
    title: "Movimientos",
    description: "Consulta tus movimientos recientes y sus categorías.",
    question: "Muéstrame mis movimientos del mes",
  },
  tarjetas: {
    title: "Tarjetas",
    description: "Administra tarjetas de demostración. No representan productos ni cuentas reales.",
    question: "¿Cuándo tengo que pagar mi tarjeta?",
  },
  pagos: {
    title: "Pagos y transferencias",
    description: "Sección simulada del prototipo; no se mueve dinero real.",
    question: "¿Qué pagos fijos tengo este mes?",
  },
  contactos: {
    title: "Contactos",
    description: "Contactos frecuentes de demostración. No hay datos reales.",
    question: "¿Cómo voy con la quincena?",
  },
  creditos: {
    title: "Créditos y simulador",
    description: "Simula pagos mensuales con resultados educativos.",
    question: "¿Cuánto pagaría por un crédito de $250,000 a 24 meses?",
  },
  ahorro: {
    title: "Metas de ahorro",
    description: "Sigue el progreso de tus metas de ahorro.",
    question: "¿Cómo voy con mis metas de ahorro?",
  },
  inversiones: {
    title: "Inversiones",
    description: "Sección simulada: sin inversiones ni rendimientos reales.",
    question: "Si ahorro 2,000 al mes, ¿cuándo juntaré 24,000?",
  },
  seguros: {
    title: "Seguros",
    description: "Información ficticia para esta demostración.",
    question: "¿Qué gastos fijos y seguros pago cada mes?",
  },
  presupuesto: {
    title: "Presupuesto",
    description: "Revisa tus gastos contra los límites que definiste.",
    question: "¿Cómo voy con mi presupuesto este mes?",
  },
  notificaciones: {
    title: "Notificaciones",
    description: "Avisos de demostración y recordatorios simulados.",
    question: "¿Tengo cargos inusuales o duplicados?",
  },
  perfil: {
    title: "Perfil y preferencias",
    description: "Preferencias de la aplicación. Este prototipo no guarda datos personales reales.",
    question: "¿Quién eres?",
  },
  ayuda: {
    title: "Ayuda y seguridad",
    description: "Este prototipo es educativo: no mueve dinero real y usa datos ficticios.",
    question: "¿Qué puedes hacer?",
  },
};
