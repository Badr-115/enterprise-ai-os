import './globals.css';

export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="ar" dir="rtl">
    <head>
      <title>نظام ذكاء المؤسسة</title>
      <meta name="description" content="ذكاء قراري موثوق قائم على الأدلة لفرق التشغيل." />
    </head>
    <body>{children}</body>
  </html>;
}
