import { LaunchDetailPage } from '@/components/pages/LaunchDetailPage'

interface Props {
  params: Promise<{ slug: string }>
}

export default async function LaunchDetail({ params }: Props) {
  const { slug } = await params
  return <LaunchDetailPage slug={slug} />
}