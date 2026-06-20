"""Generateur de configs Chart.js depuis donnees SQL."""


class ChartGenerator:

    COLORS = [
        '#FF6600', '#1a1a2e', '#FFA366', '#4a4a6a',
        '#FFD4B3', '#cc4400', '#FF8533', '#2d2d4e',
        '#FFE0CC', '#993C1D',
    ]

    def build_chart_config(self, data: list, config: dict) -> dict | None:
        if not data:
            return None

        keys = list(data[0].keys())
        label_col = config.get('label_column') or keys[0]
        value_col = config.get('value_column') or (keys[1] if len(keys) > 1 else keys[0])
        chart_type = config.get('chart_type', 'bar')
        title = config.get('title', 'Graphique')

        # S'assurer que les colonnes existent
        if label_col not in data[0]:
            label_col = keys[0]
        if value_col not in data[0]:
            value_col = keys[1] if len(keys) > 1 else keys[0]

        labels = [str(r.get(label_col, '')) for r in data]
        values = [float(r.get(value_col) or 0) for r in data]

        base_options = {
            'responsive': True,
            'maintainAspectRatio': False,
            'plugins': {
                'title': {'display': True, 'text': title, 'font': {'size': 13}},
                'legend': {'display': chart_type in ('pie', 'doughnut')},
            },
        }

        if chart_type in ('pie', 'doughnut'):
            return {
                'type': chart_type,
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'data': values,
                        'backgroundColor': (self.COLORS * 3)[:len(labels)],
                        'borderWidth': 2,
                        'borderColor': '#ffffff',
                    }],
                },
                'options': base_options,
            }

        if chart_type == 'line':
            return {
                'type': 'line',
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': value_col,
                        'data': values,
                        'borderColor': '#FF6600',
                        'backgroundColor': 'rgba(255,102,0,0.1)',
                        'tension': 0.3,
                        'fill': True,
                        'pointBackgroundColor': '#FF6600',
                    }],
                },
                'options': {**base_options, 'plugins': {**base_options['plugins'], 'legend': {'display': False}}},
            }

        # bar (defaut)
        horizontal = len(labels) > 5
        return {
            'type': 'bar',
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': value_col,
                    'data': values,
                    'backgroundColor': '#FF6600',
                    'borderRadius': 4,
                }],
            },
            'options': {
                **base_options,
                'indexAxis': 'y' if horizontal else 'x',
                'plugins': {**base_options['plugins'], 'legend': {'display': False}},
            },
        }
