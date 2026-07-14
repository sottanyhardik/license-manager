import { Link } from 'react-router-dom'
import { Button } from '@/shared/ui/button'

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-6xl font-bold text-muted-foreground">404</h1>
      <p className="text-xl font-medium">Page not found</p>
      <p className="text-muted-foreground">The page you are looking for does not exist.</p>
      <Button asChild>
        <Link to="/">Go home</Link>
      </Button>
    </div>
  )
}
