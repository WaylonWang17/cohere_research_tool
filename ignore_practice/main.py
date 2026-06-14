import asyncio

async def fetch_data(id, sleep_time):
    print(f'coroutine {id} starting to fetch data')
    await asyncio.sleep(sleep_time)
    return {'id': id, 'data': f"data from {id}"}

async def main():
    
    results = await asyncio.gather(fetch_data(1,2), fetch_data(2,3), fetch_data(3,1))    

    for result in results:
        print(result)


asyncio.run(main())