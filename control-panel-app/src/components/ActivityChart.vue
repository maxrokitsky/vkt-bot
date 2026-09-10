<script setup lang="ts">
import { computed } from 'vue'
import { VisAxis, VisStackedBar, VisXYContainer } from '@unovis/vue'
import type { ActivityPoint } from '@/client'
import type { ChartConfig } from '@/components/ui/chart'
import {
  ChartContainer,
  ChartTooltip,
  ChartCrosshair,
  ChartTooltipContent,
  componentToString,
} from '@/components/ui/chart'
import { formatDayMonth } from '@/lib/format'

/**
 * Действия по дням — дискретные суточные счётчики, поэтому столбцы, а не
 * линия: интерполяция между «0» и «5» нарисовала бы события, которых не было.
 */
const props = defineProps<{ points: ActivityPoint[] }>()

interface Point {
  date: Date
  actions: number
}

const config = {
  actions: { label: 'Действий', color: 'var(--chart-1)' },
} satisfies ChartConfig

const data = computed<Point[]>(() =>
  props.points.map((point) => ({ date: new Date(point.date), actions: point.count })),
)

/** Пустой период должен показывать шкалу 0–1, а не пустой SVG. */
const maxValue = computed(() => Math.max(1, ...data.value.map((point) => point.actions)))
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
        :y="(d: Point) => d.actions"
        :color="config.actions.color"
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
        :color="config.actions.color"
        :template="
          componentToString(config, ChartTooltipContent, {
            labelFormatter: (value: unknown) => formatDayMonth(new Date(value as number)),
          })
        "
      />
    </VisXYContainer>
  </ChartContainer>
</template>
