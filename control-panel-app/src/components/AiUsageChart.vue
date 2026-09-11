<script setup lang="ts">
import { computed } from 'vue'
import { VisAxis, VisStackedBar, VisXYContainer } from '@unovis/vue'
import type { AgentUsagePoint } from '@/client'
import type { ChartConfig } from '@/components/ui/chart'
import {
  ChartContainer,
  ChartTooltip,
  ChartCrosshair,
  ChartTooltipContent,
  componentToString,
} from '@/components/ui/chart'
import { formatDayMonth, parseLocalDate } from '@/lib/format'

/**
 * Расход токенов по дням. Столбцы, а не линия: это суточные счётчики, и
 * интерполяция между «0» и «12 000» нарисовала бы расход, которого не было.
 */
const props = defineProps<{ points: AgentUsagePoint[] }>()

interface Point {
  date: Date
  tokens: number
}

const config = {
  tokens: { label: 'Токенов', color: 'var(--chart-1)' },
} satisfies ChartConfig

const data = computed<Point[]>(() =>
  props.points.map((point) => ({ date: parseLocalDate(point.date), tokens: point.tokens })),
)

/** Период без обращений показывает шкалу 0–1, а не пустой SVG. */
const maxValue = computed(() => Math.max(1, ...data.value.map((point) => point.tokens)))
</script>

<template>
  <ChartContainer :config="config" class="aspect-auto h-[180px] w-full" :cursor="false">
    <VisXYContainer
      :data="data"
      :margin="{ left: -28, top: 8, right: 8 }"
      :y-domain="[0, maxValue]"
    >
      <VisStackedBar
        :x="(d: Point) => d.date"
        :y="(d: Point) => d.tokens"
        :color="config.tokens.color"
        :bar-max-width="24"
        :bar-padding="0.25"
        :rounded-corners="4"
      />
      <VisAxis
        type="x"
        :x="(d: Point) => d.date"
        :tick-line="false"
        :domain-line="false"
        :grid-line="false"
        :num-ticks="5"
        :tick-format="(value: number) => formatDayMonth(new Date(value))"
      />
      <VisAxis type="y" :num-ticks="3" :tick-line="false" :domain-line="false" />
      <ChartTooltip />
      <ChartCrosshair
        :color="config.tokens.color"
        :template="
          componentToString(config, ChartTooltipContent, {
            labelFormatter: (value: unknown) => formatDayMonth(new Date(value as number)),
          })
        "
      />
    </VisXYContainer>
  </ChartContainer>
</template>
