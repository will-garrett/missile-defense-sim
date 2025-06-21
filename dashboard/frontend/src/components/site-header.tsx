'use client';

import Link from "next/link";
import Image from "next/image";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export function SiteHeader() {
  return (
    <header className="w-full bg-card border-b border-border py-2 px-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Link href="/" className="flex items-center gap-4">
          <Image 
            src="/img/logo-black.svg" 
            alt="Missile Defense Simulator Logo" 
            width={40} 
            height={40} 
            className="dark:invert"
          />
          <div>
            <h1 className="text-lg font-bold tracking-tight">Missile Defense Simulator</h1>
            <p className="text-xs text-muted-foreground">Engagement Map</p>
          </div>
        </Link>
      </div>
      <nav className="flex gap-2">
        <Button variant="ghost" asChild>
          <Link href="/">Dashboard</Link>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost">Scenarios</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem asChild>
              <Link href="/scenarios">View Scenarios</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/scenarios/create">Create New Scenario</Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        
        <Button variant="ghost" asChild>
            <Link href="/system">System</Link>
        </Button>
      </nav>
    </header>
  );
} 