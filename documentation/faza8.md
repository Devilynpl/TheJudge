Faza 8: Raportowanie PR (Bot komentujący w Markdown)

Samo zablokowanie pipeline'u w CI to za mało — nikt nie chce przekopywać się przez surowe logi w zakładce GitHub Actions, żeby dowiedzieć się, dlaczego build jest czerwony. Informacja musi pojawić się natychmiast tam, gdzie programista pracuje: wprost jako komentarz pod Pull Requestem.

Cel: wygenerować czytelny raport porównawczy w formacie Markdown i automatycznie wstawiać go lub aktualizować pod PR-em po każdym pushu.

1. Struktura idealnego komentarza PR

Raport musi umożliwiać diagnozę problemu w 5 sekund:

    Status Badge: Czytelny status: zielony (EVAL PASSED) lub czerwony (EVAL BLOCKED).

    Kompaktowa tabela metryk: Wartości z main, wartości z PR oraz różnica Δ.

    Rozwijana sekcja regresji (`