const RTL_LOCALES = ["ar", "fa", "ps", "ur"];

export default function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { locale: string };
}) {
  const dir = RTL_LOCALES.includes(params.locale) ? "rtl" : "ltr";
  return (
    <div dir={dir} lang={params.locale}>
      {children}
    </div>
  );
}
