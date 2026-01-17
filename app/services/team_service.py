from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository

class TeamService:
    def __init__(self, team_repo: TeamRepository, user_repo: UserRepository):
        self.team_repo = team_repo
        self.user_repo = user_repo

    async def list(self):
        teams = await self.team_repo.list()

        # collect all member IDs
        all_member_ids = set()
        for t in teams:
            all_member_ids.update(t.get("members", []))

        # fetch users once
        users_map = await self.user_repo.get_by_ids(list(all_member_ids))

        # enrich teams
        for t in teams:
            t["members"] = [
                users_map[mid]
                for mid in t.get("members", [])
                if mid in users_map
            ]

        return teams

    async def create(self, data):
        return await self.team_repo.create(data)

    async def update(self, team_id, data):
        return await self.team_repo.update(team_id, data)

    async def toggle(self, team_id):
        return await self.team_repo.toggle(team_id)

    async def delete(self, team_id):
        return await self.team_repo.delete(team_id)
