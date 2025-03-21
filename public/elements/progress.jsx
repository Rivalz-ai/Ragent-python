// public/elements/SidebarProgressBar.jsx
import { Progress } from "@/components/ui/progress";

export default function SidebarProgressBar() {
    return (
        <div className="p-4">
            <Progress value={props.value} className="h-2" />
        </div>
    );
}

