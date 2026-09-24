# Test Sonuçları — Hafta 01

Test tanımları: [`specs/03-test-plan.md`](specs/03-test-plan.md). Her satır bir test koşusudur; bir test tekrarlanırsa yeni satır eklenir, eskisi silinmez.

| TC | Tarih | Commit | Derleme | Sonuç | Kanıt | Not |
|---|---|---|---|---|---|---|
| TC-R03 (yalnızca `.gitignore` maddesi) | 2026-09-25 | 617d98b | — | GEÇTİ | `git status --short` çıktısında `.metadata/`, `Debug/`, `Release/` yok; `git check-ignore -v` üç yolu da `.gitignore` kuralıyla eşleştiriyor | Uygulama adımı 1 çıkış testi. R03'ün diğer maddeleri adım 10'da. |
